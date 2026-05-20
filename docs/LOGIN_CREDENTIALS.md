# 🔑 Default Login Credentials

## Ready-to-Use Accounts

The application automatically creates these users on startup:

---

### 👨‍💼 Admin Account
```
Email:    officer@gov.mv
Password: super-secret-pass
```

**After login:** Auto-redirected to Admin Panel (`/admin`)

**What you can do:**
- ✅ Review pending RTI requests
- ✅ Approve/edit AI-generated drafts
- ✅ Reject requests with reasons
- ✅ View all users' requests

---

### 👤 Citizen Account
```
Email:    citizen@example.mv
Password: another-pass
```

**After login:** Redirected to File Request (`/requests/new`)

**What you can do:**
- ✅ File new RTI requests
- ✅ Track your own requests
- ✅ View responses from admins
- ✅ Check request status

---

## Quick Test

1. **Start the app:**
   ```bash
   docker compose up
   ```

2. **Login:** http://localhost:5173/login

3. **Pick an account above and login!**

---

**For more details:** See [DEFAULT_USERS.md](./DEFAULT_USERS.md)

**Security Note:** These are test accounts for development only! 🔒
