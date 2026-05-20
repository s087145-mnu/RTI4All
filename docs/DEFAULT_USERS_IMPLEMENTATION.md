# ✅ Default Users Feature - Implementation Summary

## What Was Done

Added automatic creation of default test users on application startup, so you don't have to manually create accounts every time you restart the app.

---

## Changes Made

### Backend: `backend/main.py`

Added `_create_default_users()` function that creates two users on startup:

1. **Admin User**
   - Email: `officer@gov.mv`
   - Password: `super-secret-pass`
   - Full Name: Officer Hassan
   - Role: Administrator (`is_admin: true`)

2. **Citizen User**
   - Email: `citizen@example.mv`
   - Password: `another-pass`
   - Full Name: Aishath Hassan
   - Role: Regular user (`is_admin: false`)

**Implementation:**
```python
@app.on_event("startup")
def load_data() -> None:
    # ... existing code ...
    _create_default_users()  # ← New line added

def _create_default_users() -> None:
    """Create default admin and citizen users for testing/demo purposes."""
    # Creates both users if they don't exist
    # Silently skips if they already exist (no error)
```

---

## How It Works

1. **On Backend Startup:**
   - Function runs after loading sample data
   - Attempts to create both users
   - If user already exists (duplicate email), exception is caught and ignored
   - Logs creation: `[startup] Created default admin user: officer@gov.mv`

2. **User Persistence:**
   - Users stored in-memory (like all data in this app)
   - Persist during container lifetime
   - Recreated automatically on container restart
   - No manual signup needed!

3. **Admin Privileges:**
   - `officer@gov.mv` gets admin status because it's in `ADMIN_EMAILS` env var
   - Automatic admin promotion via existing logic

---

## Testing Results

✅ **Admin Login Test:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"officer@gov.mv","password":"super-secret-pass"}'
```
**Result:** Successfully returns token with `is_admin: true`

✅ **Citizen Login Test:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"citizen@example.mv","password":"another-pass"}'
```
**Result:** Successfully returns token with `is_admin: false`

✅ **Startup Logs:**
```
[startup] Created default admin user: officer@gov.mv
[startup] Created default citizen user: citizen@example.mv
[startup] Loaded 6 requests, 1 departments, 7 FAQs...
```

---

## Usage

### Login as Admin
```
URL: http://localhost:5173/login
Email: officer@gov.mv
Password: super-secret-pass
```
→ Redirects to `/admin` panel

### Login as Citizen
```
URL: http://localhost:5173/login
Email: citizen@example.mv
Password: another-pass
```
→ Redirects to `/requests/new` page

---

## Documentation Created

📄 **`LOGIN_CREDENTIALS.md`** - Quick reference card with credentials  
📄 **`DEFAULT_USERS.md`** - Complete guide to default users  
📄 **`QUICKSTART.md`** - Updated with default user info

---

## Benefits

✅ **No Manual Setup:** Users exist immediately on startup  
✅ **Faster Testing:** Jump right into testing features  
✅ **Demo Ready:** Perfect for demos and presentations  
✅ **Consistent:** Same credentials across restarts  
✅ **Safe:** Gracefully handles duplicate creation attempts

---

## Security Considerations

⚠️ **Development Only:** These credentials are for testing

**For Production:**
1. Remove or disable `_create_default_users()` call
2. Use environment flag to control:
   ```python
   if os.environ.get("CREATE_DEFAULT_USERS") == "true":
       _create_default_users()
   ```
3. Or delete the function entirely
4. Implement proper user management system

---

## Verification Commands

**Check users were created:**
```bash
docker compose logs backend | grep "Created default"
```

**Test admin login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"officer@gov.mv","password":"super-secret-pass"}' \
  | python3 -m json.tool
```

**Test citizen login:**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"citizen@example.mv","password":"another-pass"}' \
  | python3 -m json.tool
```

---

## Quick Start

1. **Start the app:**
   ```bash
   docker compose up
   ```

2. **Wait for startup logs:**
   ```
   [startup] Created default admin user: officer@gov.mv
   [startup] Created default citizen user: citizen@example.mv
   ```

3. **Login immediately:**
   - Go to http://localhost:5173/login
   - Use credentials from above
   - Start testing!

---

## Summary

✅ **Feature Working:** Both users created automatically  
✅ **Admin Access:** `officer@gov.mv` has full admin privileges  
✅ **Citizen Access:** `citizen@example.mv` has regular user access  
✅ **Auto-redirect:** Admins → `/admin`, Citizens → `/requests/new`  
✅ **Zero Configuration:** Works out of the box

**You're all set! Just login and start testing.** 🚀
