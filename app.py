from flask import Flask, request, jsonify, render_template
import re
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///civicai.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    location = db.Column(db.String(100), nullable=True)
    contribution_score = db.Column(db.Integer, default=0)
    password_hash = db.Column(db.String(128))
    mobile = db.Column(db.String(15))
    issues = db.relationship('Issue', backref='author', lazy=True)

class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    categories = db.Column(db.JSON, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='reported')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    votes_confirm = db.Column(db.Integer, default=0)
    votes_reject = db.Column(db.Integer, default=0)
    trust_score = db.Column(db.Float, default=0.5)
    primary_dept = db.Column(db.String(100))
    secondary_dept = db.Column(db.String(100))
    recommendation = db.Column(db.Text)
    complaint_generated = db.Column(db.Boolean, default=False)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)  # 'confirm' or 'reject'
    __table_args__ = (db.UniqueConstraint('issue_id', 'user_id', name='unique_vote'),)

class Update(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issue.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    update_type = db.Column(db.String(20), nullable=False)  # 'resolved' / 'worse' / 'same'
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), unique=True, nullable=False)
    primary_dept = db.Column(db.String(100), nullable=False)
    secondary_dept = db.Column(db.String(100), nullable=False)

# Create database tables and seed departments
with app.app_context():
    db.create_all()
    def seed_departments():
        defaults = [
            {'category': 'Waste Management', 'primary_dept': 'Municipal Corporation', 'secondary_dept': 'Health Department'},
            {'category': 'Water Issue', 'primary_dept': 'Water Department', 'secondary_dept': 'Emergency Services'},
            {'category': 'Electricity', 'primary_dept': 'Electricity Board', 'secondary_dept': 'Fire Department'},
            {'category': 'Road Damage', 'primary_dept': 'Highway Authority', 'secondary_dept': 'Traffic Police'},
            {'category': 'General Civic Issue', 'primary_dept': 'Municipal Corporation', 'secondary_dept': 'Police'}
        ]
        for item in defaults:
            existing = Department.query.filter_by(category=item['category']).first()
            if not existing:
                db.session.add(Department(**item))
        db.session.commit()

    seed_departments()

# Rule-based classification functions

# Rule-based classification functions
def classify_problem(description):
    desc_lower = description.lower()
    
    # Categories based on keywords
    if any(word in desc_lower for word in ['garbage', 'waste', 'trash', 'overflow', 'dump']):
        return 'Waste Management'
    elif any(word in desc_lower for word in ['water', 'leak', 'pipe', 'flood', 'sewage']):
        return 'Water Issue'
    elif any(word in desc_lower for word in ['electricity', 'power', 'light', 'outage', 'wire']):
        return 'Electricity'
    elif any(word in desc_lower for word in ['road', 'pothole', 'damage', 'street', 'traffic']):
        return 'Road Damage'
    else:
        return 'General Civic Issue'

def assign_priority(description):
    desc_lower = description.lower()
    
    # High priority keywords
    if any(word in desc_lower for word in ['dangerous', 'urgent', 'emergency', 'hazard', 'accident', 'fire', 'explosion']):
        return 'High'
    # Medium priority
    elif any(word in desc_lower for word in ['important', 'serious', 'broken', 'damaged', 'overflow']):
        return 'Medium'
    else:
        return 'Low'

def assign_departments(category, priority):
    departments = {
        'Waste Management': {'High': ('Municipal Corporation', 'Health Department'), 'Medium': ('CleanCity NGO', 'Municipal Corporation'), 'Low': ('Local Volunteers', 'Community Center')},
        'Water Issue': {'High': ('Water Department', 'Emergency Services'), 'Medium': ('Water NGO', 'Water Department'), 'Low': ('Local Plumbers', 'Water Department')},
        'Electricity': {'High': ('Electricity Board', 'Fire Department'), 'Medium': ('Power NGO', 'Electricity Board'), 'Low': ('Local Electricians', 'Electricity Board')},
        'Road Damage': {'High': ('Highway Authority', 'Traffic Police'), 'Medium': ('Road NGO', 'Highway Authority'), 'Low': ('Local Contractors', 'Municipal Corporation')},
        'General Civic Issue': {'High': ('Municipal Corporation', 'Police'), 'Medium': ('Local NGO', 'Municipal Corporation'), 'Low': ('Community Volunteers', 'Local Authorities')}
    }
    primary, secondary = departments.get(category, {}).get(priority, ('Local Authorities', 'Municipal Corporation'))
    return primary, secondary

def generate_recommendation(category, priority):
    recommendations = {
        'Waste Management': {
            'High': 'Avoid the area and report immediately to prevent health hazards',
            'Medium': 'Contact local cleanup services and monitor the situation',
            'Low': 'Report to local authorities for scheduled cleanup'
        },
        'Water Issue': {
            'High': 'Stop using water immediately and contact emergency services',
            'Medium': 'Report to water department and avoid contaminated areas',
            'Low': 'Monitor the issue and report for repair scheduling'
        },
        'Electricity': {
            'High': 'Stay away from wires and contact emergency electricity services',
            'Medium': 'Report outage and avoid using electrical appliances',
            'Low': 'Report for scheduled repair'
        },
        'Road Damage': {
            'High': 'Avoid the area and use alternative routes to prevent accidents',
            'Medium': 'Report to traffic authorities and mark the area',
            'Low': 'Report for future maintenance'
        },
        'General Civic Issue': {
            'High': 'Contact emergency services immediately',
            'Medium': 'Report to relevant local authorities',
            'Low': 'Document and report for community awareness'
        }
    }
    return recommendations.get(category, {}).get(priority, 'Please report to local authorities')

@app.route('/')
def home():
    return render_template('app.html')

@app.route('/login')
def login_page():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard_page():
    issues = Issue.query.order_by(Issue.created_at.desc()).limit(10).all()
    total_issues = Issue.query.count()
    solved_issues = Issue.query.filter_by(status='resolved').count()
    pending_issues = Issue.query.filter_by(status='reported').count()
    return render_template('dashboard.html', issues=issues, total_issues=total_issues, solved_issues=solved_issues, pending_issues=pending_issues)

@app.route('/app')
def app_page():
    # Check if user is logged in (simple check)
    # In production, use proper session management
    return render_template('app.html')

@app.route('/logout')
def logout():
    # Simple logout - in production, clear server session
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_problem():
    data = request.get_json()
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    categories = data.get('categories', [])
    location = data.get('location', '').strip()
    user_name = data.get('user_name', '').strip()

    if not title or not description or not location or not user_name:
        return jsonify({'error': 'Please provide title, description, location, and user_name'}), 400

    if not isinstance(categories, list):
        categories = [categories] if categories else []

    user = User.query.filter_by(name=user_name).first()
    if not user:
        user = User(name=user_name, location=location)
        db.session.add(user)
        db.session.commit()

    system_category = classify_problem(description)
    if categories and any(c != 'Not sure' for c in categories):
        system_category = categories[0] if categories[0] != 'Not sure' else system_category

    if not categories:
        categories = [system_category]

    priority = assign_priority(description)
    primary_dept, secondary_dept = assign_departments(system_category, priority)
    recommendation = generate_recommendation(system_category, priority)

    issue = Issue(
        title=title,
        description=description,
        categories=categories,
        location=location,
        priority=priority,
        status='reported',
        created_by=user.id,
        primary_dept=primary_dept,
        secondary_dept=secondary_dept,
        recommendation=recommendation
    )
    db.session.add(issue)
    db.session.commit()

    generate_complaint_pdf(issue)

    result = {
        'issue_id': issue.id,
        'categories': issue.categories,
        'priority': issue.priority,
        'primary_dept': issue.primary_dept,
        'secondary_dept': issue.secondary_dept,
        'recommendation': issue.recommendation,
        'complaint_url': f'/static/complaint_{issue.id}.pdf'
    }

    return jsonify(result)

def generate_complaint_pdf(issue):
    filename = f'complaint_{issue.id}.pdf'
    filepath = os.path.join('static', filename)
    os.makedirs('static', exist_ok=True)
    
    c = canvas.Canvas(filepath, pagesize=letter)
    c.drawString(100, 750, "Civic Issue Complaint")
    c.drawString(100, 730, f"Issue ID: {issue.id}")
    c.drawString(100, 710, f"Title: {issue.title}")
    c.drawString(100, 690, f"Location: {issue.location}")
    c.drawString(100, 670, f"Categories: {', '.join(issue.categories)}")
    c.drawString(100, 650, f"Priority: {issue.priority}")
    c.drawString(100, 630, f"Description: {issue.description}")
    c.drawString(100, 610, f"Primary Department: {issue.primary_dept}")
    c.drawString(100, 590, f"Secondary Department: {issue.secondary_dept}")
    c.drawString(100, 570, f"Recommendation: {issue.recommendation}")
    c.drawString(100, 550, f"Reported by: {issue.author.name}")
    c.drawString(100, 530, f"Date: {issue.created_at.strftime('%Y-%m-%d')}")
    c.save()
    issue.complaint_generated = True
    db.session.commit()

@app.route('/api/issues', methods=['GET'])
def get_issues():
    location = request.args.get('location', '').strip()
    if not location:
        return jsonify({'error': 'Location required'}), 400
    
    issues = Issue.query.filter_by(location=location).order_by(Issue.created_at.desc()).all()
    issues_data = []
    for issue in issues:
        issues_data.append({
            'id': issue.id,
            'title': issue.title,
            'description': issue.description,
            'categories': issue.categories,
            'location': issue.location,
            'priority': issue.priority,
            'status': issue.status,
            'trust_score': issue.trust_score,
            'votes_confirm': issue.votes_confirm,
            'votes_reject': issue.votes_reject,
            'primary_dept': issue.primary_dept,
            'secondary_dept': issue.secondary_dept,
            'recommendation': issue.recommendation,
            'created_by': issue.author.name if issue.author else None,
            'created_at': issue.created_at.isoformat(),
            'complaint_url': f'/static/complaint_{issue.id}.pdf' if issue.complaint_generated else None
        })
    
    return jsonify({'issues': issues_data})

@app.route('/api/vote/<int:issue_id>', methods=['POST'])
def vote_issue(issue_id):
    data = request.get_json()
    user_name = data.get('user_name', '').strip()
    vote_type = data.get('vote_type', '').strip()  # 'confirm' or 'reject'
    
    if not user_name or vote_type not in ['confirm', 'reject']:
        return jsonify({'error': 'Invalid data'}), 400
    
    user = User.query.filter_by(name=user_name).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404
    
    existing_vote = Vote.query.filter_by(issue_id=issue_id, user_id=user.id).first()
    if existing_vote:
        if existing_vote.vote_type == vote_type:
            return jsonify({'error': 'Already voted'}), 400
        if existing_vote.vote_type == 'confirm':
            issue.votes_confirm -= 1
        else:
            issue.votes_reject -= 1
        existing_vote.vote_type = vote_type
    else:
        vote = Vote(issue_id=issue_id, user_id=user.id, vote_type=vote_type)
        db.session.add(vote)
    
    if vote_type == 'confirm':
        issue.votes_confirm += 1
    else:
        issue.votes_reject += 1
    
    total_votes = issue.votes_confirm + issue.votes_reject
    if total_votes > 0:
        issue.trust_score = issue.votes_confirm / total_votes
    
    user.contribution_score += 1
    db.session.commit()
    return jsonify({'success': True, 'votes_confirm': issue.votes_confirm, 'votes_reject': issue.votes_reject, 'trust_score': issue.trust_score})

@app.route('/api/update-status/<int:issue_id>', methods=['POST'])
def update_status(issue_id):
    data = request.get_json()
    user_name = data.get('user_name', '').strip()
    update_type = data.get('update_type', '').strip()  # 'resolved', 'worse', 'same'
    comment = data.get('comment', '').strip()
    
    if not user_name or update_type not in ['resolved', 'worse', 'same']:
        return jsonify({'error': 'Invalid data'}), 400
    
    user = User.query.filter_by(name=user_name).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404
    
    issue.status = update_type
    issue.updated_at = datetime.utcnow()
    
    status_update = Update(
        issue_id=issue_id,
        user_id=user.id,
        update_type=update_type,
        comment=comment
    )
    db.session.add(status_update)
    user.contribution_score += 1
    db.session.commit()
    
    return jsonify({'success': True, 'status': update_type})

@app.route('/api/generate-complaint/<int:issue_id>', methods=['GET'])
def generate_complaint(issue_id):
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404
    
    filename = f'complaint_{issue_id}.pdf'
    filepath = os.path.join('static', filename)
    os.makedirs('static', exist_ok=True)
    
    c = canvas.Canvas(filepath, pagesize=letter)
    c.drawString(100, 750, "Civic Issue Complaint")
    c.drawString(100, 730, f"Issue ID: {issue.id}")
    c.drawString(100, 710, f"Title: {issue.title}")
    c.drawString(100, 690, f"Location: {issue.location}")
    c.drawString(100, 670, f"Categories: {', '.join(issue.categories)}")
    c.drawString(100, 650, f"Priority: {issue.priority}")
    c.drawString(100, 630, f"Description: {issue.description}")
    c.drawString(100, 610, f"Primary Department: {issue.primary_dept}")
    c.drawString(100, 590, f"Secondary Department: {issue.secondary_dept}")
    c.drawString(100, 570, f"Recommendation: {issue.recommendation}")
    c.drawString(100, 550, f"Reported by: {issue.author.name}")
    c.drawString(100, 530, f"Date: {issue.created_at.strftime('%Y-%m-%d')}")
    c.save()
    
    issue.complaint_generated = True
    db.session.commit()
    
    return jsonify({'complaint_url': f'/static/{filename}'})

@app.route('/api/escalate/<int:issue_id>', methods=['POST'])
def escalate_issue(issue_id):
    issue = Issue.query.get(issue_id)
    if not issue:
        return jsonify({'error': 'Issue not found'}), 404
    
    if issue.status != 'resolved' and issue.trust_score > 0.7 and issue.votes_confirm > issue.votes_reject:
        issue.status = 'escalated'
        issue.last_updated = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'status': 'escalated'})
    else:
        return jsonify({'error': 'Cannot escalate'}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)