# Summary of Changes

## Issues Fixed

### 1. Phone Number Validation Error on Signup
**Problem:** The signup form showed "phone number is required" even after entering it.

**Root Cause:** The `signup` function in `AuthProvider` only passed `email`, `password`, and `full_name` to the backend API, ignoring `phone_number`, `present_address`, and `id_card`.

**Solution:** Updated the `signup` function to accept and pass all required fields:
```javascript
async ({ email, password, full_name, present_address, phone_number, id_card }) => {
  const data = await post("/api/auth/signup", {
    email,
    password,
    full_name,
    present_address,
    phone_number,
    id_card,
  });
  // ...
}
```

### 2. Admin User Auto-redirect
**Problem:** Admin users needed to be automatically redirected to the admin panel after signup/login.

**Solution:** 
- Updated `SignupPage` to redirect admins to `/admin` and regular users to `/requests/new`
- Updated `LoginPage` to do the same based on `user.is_admin` flag
- The redirect happens both in the `useEffect` and after successful authentication

## New Files Created

### 1. `.env` - Environment Configuration
Contains the runtime configuration including:
- `ANTHROPIC_API_KEY` - API key for AI responses
- `JWT_SECRET_KEY` - Secret for JWT token signing
- `ADMIN_EMAILS` - Comma-separated list of admin emails (default: `officer@gov.mv`)

### 2. `.env.example` - Environment Template
Template file for developers to copy and configure their own `.env` file.

### 3. `ADMIN_SETUP.md` - Admin Setup Guide
Comprehensive guide for setting up and managing admin users, including:
- Quick setup instructions
- Admin features overview
- Adding new admins
- Security notes
- Troubleshooting guide

## Files Modified

### 1. `frontend/src/App.jsx`
**Changes:**
- Fixed `signup` function to pass all required fields
- Updated `SignupPage` to redirect admins to `/admin`
- Updated `LoginPage` to redirect admins to `/admin`
- Both pages now check `user.is_admin` flag for routing decisions

### 2. `docker-compose.yml`
**Changes:**
- Added `env_file: .env` to backend service
- Removed explicit environment variable declarations (now loaded from .env)
- Simplified configuration management

### 3. `README.md`
**Changes:**
- Updated "Configure environment" section with new `.env` file approach
- Added step-by-step instructions for copying `.env.example`
- Added "Admin Setup" section explaining automatic admin privileges and redirects

## How It Works

### Admin User Flow

1. **Configuration**: Add email to `ADMIN_EMAILS` in `.env` file
   ```bash
   ADMIN_EMAILS=officer@gov.mv,supervisor@gov.mv
   ```

2. **Signup**: User signs up with an email listed in `ADMIN_EMAILS`
   - Backend checks email against `ADMIN_EMAILS` (case-insensitive)
   - Sets `is_admin: true` in user record
   - Returns user object with admin flag

3. **Redirect**: Frontend checks `user.is_admin`
   - If `true`: Redirect to `/admin` (admin panel)
   - If `false`: Redirect to `/requests/new` (new request form)

4. **Login**: Same redirect logic applies on subsequent logins
   - Existing users are retrofitted with admin status if their email is added to `ADMIN_EMAILS`

### Regular User Flow

1. **Signup**: User signs up with any email not in `ADMIN_EMAILS`
   - Backend sets `is_admin: false`
   - Returns user object without admin privileges

2. **Redirect**: Frontend redirects to `/requests/new`
   - User can file RTI requests
   - Cannot access admin endpoints

## Testing

To test admin functionality:

1. Ensure `.env` has `ADMIN_EMAILS=officer@gov.mv`
2. Start the application: `docker compose up`
3. Sign up with email: `officer@gov.mv`
4. Fill in all required fields (name, phone, address, password)
5. Upon successful signup, should be redirected to `/admin`
6. Admin panel should display pending requests for review

## Security Considerations

- `.env` file is gitignored to prevent committing secrets
- `.env.example` serves as a template (safe to commit)
- Admin emails are case-insensitive for user convenience
- JWT tokens include the `is_admin` flag for authorization
- Admin status can be retrofitted on next login if email is added after signup
