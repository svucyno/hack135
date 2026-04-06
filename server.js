const express = require('express');
const path = require('path');
const bcrypt = require('bcryptjs');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
// simple CORS header to allow easy testing
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  next();
});

// Serve static files (so you can open http://localhost:3000/login.html)
app.use(express.static(path.join(__dirname)));

// In-memory stores (replace with DB in production)
const users = {}; // userId -> { passwordHash, mobile }
const otps = {};  // userId -> { otp, expiresAt, verified }

function generateOtp() {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

function maskMobile(m) {
  if (!m) return '';
  const digits = m.replace(/\D/g, '');
  if (digits.length <= 4) return m;
  return '****' + digits.slice(-4);
}

// Register
app.post('/api/register', (req, res) => {
  const { userId, password, mobile } = req.body || {};
  if (!userId || !password) return res.status(400).json({ success: false, message: 'userId and password required' });
  if (users[userId]) return res.status(400).json({ success: false, message: 'User already exists' });

  const hash = bcrypt.hashSync(password, 8);
  users[userId] = { passwordHash: hash, mobile: mobile || null };
  console.log(`Registered user: ${userId} -> mobile=${mobile}`);
  return res.status(201).json({ success: true, message: 'Registered' });
});

// Login
app.post('/api/login', (req, res) => {
  const { userId, password } = req.body || {};
  if (!userId || !password) return res.status(400).json({ success: false, message: 'userId and password required' });
  const u = users[userId];
  if (!u) return res.status(401).json({ success: false, message: 'Invalid credentials' });
  const ok = bcrypt.compareSync(password, u.passwordHash);
  if (!ok) return res.status(401).json({ success: false, message: 'Invalid credentials' });
  return res.json({ success: true, message: 'Login successful' });
});

// Send OTP
app.post('/api/send-otp', (req, res) => {
  const { userId } = req.body || {};
  if (!userId) return res.status(400).json({ success: false, message: 'userId required' });
  const u = users[userId];
  if (!u) return res.status(404).json({ success: false, message: 'User not found' });

  const otp = generateOtp();
  const expiresAt = Date.now() + 5 * 60 * 1000; // 5 minutes
  otps[userId] = { otp, expiresAt, verified: false };

  // In real app, send SMS via provider. Here we log to console for testing.
  console.log(`SEND SMS to ${u.mobile || 'unknown'} -> OTP=${otp}`);

  return res.json({ success: true, maskedMobile: maskMobile(u.mobile) });
});

// Resend OTP
app.post('/api/resend-otp', (req, res) => {
  const { userId } = req.body || {};
  if (!userId) return res.status(400).json({ success: false, message: 'userId required' });
  const u = users[userId];
  if (!u) return res.status(404).json({ success: false, message: 'User not found' });

  const otp = generateOtp();
  const expiresAt = Date.now() + 5 * 60 * 1000; // 5 minutes
  otps[userId] = { otp, expiresAt, verified: false };
  console.log(`RESEND SMS to ${u.mobile || 'unknown'} -> OTP=${otp}`);
  return res.json({ success: true, maskedMobile: maskMobile(u.mobile) });
});

// Verify OTP
app.post('/api/verify-otp', (req, res) => {
  const { userId, otp } = req.body || {};
  if (!userId || !otp) return res.status(400).json({ success: false, message: 'userId and otp required' });
  const record = otps[userId];
  if (!record) return res.status(400).json({ success: false, message: 'No OTP requested' });
  if (Date.now() > record.expiresAt) return res.status(400).json({ success: false, message: 'OTP expired' });
  if (record.otp !== otp) return res.status(400).json({ success: false, message: 'Invalid OTP' });
  record.verified = true;
  return res.json({ success: true });
});

// Reset password (requires OTP verification)
app.post('/api/reset-password', (req, res) => {
  const { userId, password } = req.body || {};
  if (!userId || !password) return res.status(400).json({ success: false, message: 'userId and password required' });
  const u = users[userId];
  if (!u) return res.status(404).json({ success: false, message: 'User not found' });
  const record = otps[userId];
  if (!record || !record.verified) return res.status(400).json({ success: false, message: 'OTP not verified' });

  const hash = bcrypt.hashSync(password, 8);
  users[userId].passwordHash = hash;
  // clear OTP record
  delete otps[userId];
  console.log(`Password reset for ${userId}`);
  return res.json({ success: true, message: 'Password reset' });
});

app.listen(PORT, () => {
  console.log(`Auth server running on http://localhost:${PORT}`);
});
