# Troubleshooting: Existing Account Not Admin

## Problem
You created an account with `officer@gov.mv` **before** setting up the `ADMIN_EMAILS` environment variable, so the account doesn't have admin privileges.

## Quick Fix (Recommended)

The backend has a **retrofit mechanism** that automatically upgrades accounts to admin on login if their email is in `ADMIN_EMAILS`.

### Steps:

1. **Verify .env configuration**:
   ```bash
   # Run the diagnostic script
   ./check-admin.sh
   ```

   Or manually check that `.env` contains:
   ```bash
   ADMIN_EMAILS=officer@gov.mv
   ```

2. **Restart the backend** to load the new environment variable:
   ```bash
   docker compose restart backend
   ```

3. **Verify backend loaded the config**:
   ```bash
   docker exec rti4all-backend printenv | grep ADMIN_EMAILS
   ```
   
   You should see: `ADMIN_EMAILS=officer@gov.mv`

4. **Log out** from the frontend:
   - Click your profile/logout button
   - Or clear browser local storage: `localStorage.clear()` in browser console

5. **Log back in** with `officer@gov.mv`:
   - The retrofit logic will detect your email in `ADMIN_EMAILS`
   - It will set `is_admin: true` on your user record
   - You'll be redirected to `/admin`

## Alternative: Fresh Start

If the retrofit doesn't work, you can start with a clean slate:

### Steps:

1. **Stop and remove containers**:
   ```bash
   docker compose down
   ```

2. **Verify .env has ADMIN_EMAILS**:
   ```bash
   cat .env | grep ADMIN_EMAILS
   ```
   
   Should show: `ADMIN_EMAILS=officer@gov.mv`

3. **Start fresh**:
   ```bash
   docker compose up
   ```

4. **Sign up again** at http://localhost:5173/signup:
   - Email: `officer@gov.mv`
   - Fill in all required fields
   - You'll automatically be redirected to `/admin`

## Verify Admin Status

After logging in, you can verify your admin status by checking the browser console:

```javascript
// Open browser console (F12)
JSON.parse(localStorage.getItem('auth'))
```

You should see:
```json
{
  "user": {
    "email": "officer@gov.mv",
    "is_admin": true,
    ...
  },
  "token": "..."
}
```

## Backend Retrofit Code

The retrofit happens in `backend/auth.py` at login:

```python
def authenticate_user(*, email: str, password: str) -> UserPublic:
    # ... authentication logic ...
    
    # Retrofit is_admin if the email was added to ADMIN_EMAILS after signup.
    if _is_admin_email(record.email) and not record.is_admin:
        record.is_admin = True
    
    return _to_public(record)
```

## Still Not Working?

If you're still having issues:

1. **Check browser console** for any JavaScript errors
2. **Check backend logs**:
   ```bash
   docker compose logs backend | grep -i admin
   ```

3. **Verify the API response** when logging in:
   - Open browser DevTools > Network tab
   - Log in
   - Find the POST request to `/api/auth/login`
   - Check the response - `user.is_admin` should be `true`

4. **Manual check of user store** (for debugging):
   The user store is in-memory, but you can add a debug endpoint or check logs to see what's stored.

## Need Help?

Run the diagnostic script:
```bash
./check-admin.sh
```

This will check:
- ✓ .env file exists
- ✓ ADMIN_EMAILS is configured
- ✓ officer@gov.mv is in the list
- ✓ Backend container is running
- ✓ Environment variables loaded in container
