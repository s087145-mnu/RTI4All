# Admin Setup Guide

## Overview
The RTI4All system uses email-based admin authentication. Users who sign up with emails listed in the `ADMIN_EMAILS` environment variable are automatically granted admin privileges.

## Quick Setup

### 1. Configure Admin Emails

Edit the `.env` file in the project root:

```bash
ADMIN_EMAILS=officer@gov.mv,supervisor@gov.mv,another.admin@gov.mv
```

You can list multiple admin emails separated by commas. Email matching is **case-insensitive**.

### 2. Start the Application

```bash
docker compose up
```

The backend will load the admin emails on startup.

### 3. Create Admin Account

1. Navigate to the signup page: `http://localhost:5173/signup`
2. Fill in the registration form with one of the admin emails (e.g., `officer@gov.mv`)
3. Complete the registration with:
   - **Name:** Officer Hassan (or your name)
   - **Email:** officer@gov.mv (must match ADMIN_EMAILS)
   - **Phone:** +960 3001000 (or your number)
   - **Address:** Ministry HQ, Male' (or your address)
   - **Password:** Your secure password (min 8 characters)

### 4. Automatic Redirect

After successful signup, admin users are automatically redirected to:
- **Admin Panel** (`/admin`) - For reviewing and managing RTI requests

Regular users (non-admin emails) are redirected to:
- **New Request** (`/requests/new`) - For filing RTI requests

## Admin Features

Once logged in as an admin, you can:

1. **Review Pending Requests** - View all requests awaiting human review
2. **Approve AI Drafts** - Approve automatically generated responses
3. **Edit Responses** - Modify AI-generated responses before approval
4. **Reject Requests** - Reject requests with a reason
5. **View Request Details** - Access full citizen information and request history

## Adding New Admins

To add a new admin email after the system is running:

1. Stop the application: `docker compose down`
2. Edit `.env` and add the new email to `ADMIN_EMAILS`
3. Restart: `docker compose up`
4. The new admin can now sign up with that email

**Note:** Existing users who signed up before being added to `ADMIN_EMAILS` will be retrofitted with admin privileges on their next login.

## Testing Admin Access

You can verify admin setup using the test credentials from the test suite:

```bash
# Test admin credentials
Email: officer@gov.mv
Password: super-secret-pass (or your chosen password)
```

Navigate to `/admin` after logging in to access the admin panel.

## Security Notes

- **Never commit `.env` to version control** - It contains sensitive configuration
- Use strong, unique passwords for admin accounts
- Regularly review the list of admin emails
- The JWT secret key should be high-entropy and kept secret
- In production, use HTTPS and secure the `ADMIN_EMAILS` configuration

## Troubleshooting

### Admin not redirected to admin panel
- Verify the email matches exactly (case-insensitive) with `ADMIN_EMAILS`
- Check that the `.env` file is loaded by Docker Compose
- Try logging out and logging back in
- Check backend logs for admin email configuration on startup

### Cannot access admin endpoints
- Ensure the user's `is_admin` field is `true` (visible in API response)
- Verify the JWT token includes admin privileges
- Check that you're using the correct Bearer token in requests

### Email already registered
- If you need to change an email to admin, you'll need to:
  1. Clear the backend's user store (restart with fresh data)
  2. Or add the email to `ADMIN_EMAILS` and have the user log in again
