# CivicAI Auth Server - API README

This document describes the local auth server added for the `login.html` UI.

Endpoints (local):

- POST /api/register
  - Body: { userId, password, mobile }
  - Response: { success: true }
- POST /api/login
  - Body: { userId, password }
  - Response: { success: true }
- POST /api/send-otp
  - Body: { userId }
  - Response: { success: true, maskedMobile }
- POST /api/resend-otp
  - Body: { userId }
  - Response: { success: true, maskedMobile }
- POST /api/verify-otp
  - Body: { userId, otp }
  - Response: { success: true }
- POST /api/reset-password
  - Body: { userId, password }
  - Response: { success: true }

How it works locally
- The server stores data in memory (no DB). Restarting the server clears users and OTPs.
- OTP values are NOT returned to the client (they are logged to the server console). This is intentional for a local test server — replace with a real SMS gateway for production.

To run (PowerShell):

```powershell
cd d:\civicai
npm install
node server.js
```

Open the UI at: http://localhost:3001/login.html

If you open `login.html` directly from the filesystem (file://), the page is configured to contact the local API at `http://localhost:3001`.

Security note: This is a minimal example for local development only. Do not use it in production without hardening.
