# Default Test Users

The application automatically creates two default users on startup for testing and demo purposes.

## Default Users

### 1. Admin User
**Purpose:** Access the admin panel, review and respond to RTI requests

- **Email:** `officer@gov.mv`
- **Password:** `super-secret-pass`
- **Name:** Officer Hassan
- **Role:** Administrator
- **Access:** Full admin panel at `/admin`

**Login URL:** http://localhost:5173/login

After login, you'll be automatically redirected to the admin panel.

### 2. Citizen User
**Purpose:** File RTI requests, track submissions

- **Email:** `citizen@example.mv`
- **Password:** `another-pass`
- **Name:** Aishath Hassan
- **Address:** H. Sunset, Hithadhoo, Addu City
- **Phone:** +960 7777777
- **ID Card:** A099887
- **Role:** Regular user

**Login URL:** http://localhost:5173/login

After login, you'll be redirected to the "New Request" page.

## Quick Start Testing

### Test as Admin

1. **Login:**
   ```
   Email: officer@gov.mv
   Password: super-secret-pass
   ```

2. **You'll be at:** `/admin` (Admin Review Inbox)

3. **What you can do:**
   - View all pending requests awaiting review
   - Approve AI-generated drafts
   - Edit responses before approval
   - Reject requests with reasons
   - View all users' requests

### Test as Citizen

1. **Login:**
   ```
   Email: citizen@example.mv
   Password: another-pass
   ```

2. **You'll be at:** `/requests/new` (File RTI Request)

3. **What you can do:**
   - File new RTI requests
   - View your own requests (not others')
   - Track request status
   - See responses from admins

## User Creation

These users are automatically created when the backend starts up.

**Location:** `RTI4All/backend/main.py` in the `_create_default_users()` function

**Behavior:**
- Users are created on first startup
- If users already exist, creation is skipped (no error)
- Works with in-memory storage (users persist during container lifetime)
- Recreated on container restart (in-memory storage)

## Security Notes

⚠️ **For Development Only**

These default users are **only for testing and development**. In production:

1. **Remove default user creation** or protect with environment flag
2. **Use strong, unique passwords**
3. **Don't use predictable credentials**
4. **Implement proper user management**

## Changing Default Credentials

To change the default users, edit `backend/main.py`:

```python
def _create_default_users() -> None:
    """Create default admin and citizen users for testing/demo purposes."""
    from auth import create_user
    
    # Default admin user
    admin_email = "your-admin@example.com"  # ← Change here
    try:
        create_user(
            email=admin_email,
            password="your-secure-password",  # ← Change here
            full_name="Your Name",            # ← Change here
            # ... etc
        )
    # ... rest of the code
```

Then restart the backend:
```bash
docker compose restart backend
```

## Verifying Users Were Created

Check the startup logs:
```bash
docker compose logs backend | grep "Created default"
```

You should see:
```
[startup] Created default admin user: officer@gov.mv
[startup] Created default citizen user: citizen@example.mv
```

## Testing Login

### Quick Test Script

You can verify users are created by attempting login:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "officer@gov.mv",
    "password": "super-secret-pass"
  }'
```

Successful response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "email": "officer@gov.mv",
    "full_name": "Officer Hassan",
    "is_admin": true,
    ...
  }
}
```

## Admin User Privileges

The admin user (`officer@gov.mv`) automatically gets admin privileges because:

1. The email is listed in `ADMIN_EMAILS` environment variable (`.env`)
2. The `create_user` function checks against this list
3. Sets `is_admin: true` on user creation

## Workflow Examples

### Complete Admin Workflow

1. Login as admin (`officer@gov.mv`)
2. View pending requests at `/admin`
3. Click on a request
4. Review AI draft or write manual response
5. Approve/reject
6. Citizen sees the response

### Complete Citizen Workflow

1. Login as citizen (`citizen@example.mv`)
2. File RTI request at `/requests/new`
3. Check status at `/requests`
4. Click on your request to see details
5. Wait for admin response
6. View response when status changes to "Responded"

## Multiple Test Users

Want more test users? Add them to the `_create_default_users()` function:

```python
# Additional test citizen
try:
    create_user(
        email="test-user@example.mv",
        password="test-pass",
        full_name="Test User",
        present_address="Test Address",
        phone_number="+960 9999999",
    )
    print(f"[startup] Created test user: test-user@example.mv")
except Exception:
    pass
```

## Disabling Default Users

To disable automatic user creation (for production):

Option 1: Comment out the function call in `load_data()`:
```python
# _create_default_users()  # Disabled for production
```

Option 2: Add an environment check:
```python
if os.environ.get("CREATE_DEFAULT_USERS", "false").lower() == "true":
    _create_default_users()
```

## Summary

- ✅ No need to manually sign up test users
- ✅ Works immediately on startup
- ✅ Admin and citizen accounts ready to use
- ✅ Perfect for development and demos
- ⚠️ Remember to disable or secure for production!
