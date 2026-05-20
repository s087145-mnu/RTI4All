# Quick Start Guide

## For First-Time Setup

### 1. Copy Environment Configuration
```bash
cp .env.example .env
```

### 2. Edit `.env` File
Replace the placeholder values with your actual credentials:

```bash
# Replace with your actual Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here

# Generate a secure secret
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Set admin emails (default is officer@gov.mv)
ADMIN_EMAILS=officer@gov.mv
```

### 3. Start the Application
```bash
docker compose up
```

Wait for both services to start:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## Creating Your First Admin Account

### Option 1: Use the Default Admin Email

1. Open http://localhost:5173/signup
2. Sign up with these details:
   - **Email**: `officer@gov.mv`
   - **Name**: Your name
   - **Phone**: Your phone number
   - **Address**: Your address
   - **Password**: At least 8 characters

3. You'll automatically be redirected to `/admin` panel

### Option 2: Use Your Own Email

1. Edit `.env` and add your email:
   ```bash
   ADMIN_EMAILS=your-email@example.com
   ```

2. Restart the application:
   ```bash
   docker compose down
   docker compose up
   ```

3. Sign up with your email at http://localhost:5173/signup

4. You'll be redirected to the admin panel

## Testing the System

### As an Admin User

1. **Access Admin Panel**: Navigate to http://localhost:5173/admin
2. **View Pending Requests**: See all requests waiting for review
3. **Review Request**: Click on a request to see details
4. **Approve/Edit/Reject**: Take action on AI-generated drafts

### As a Regular User

1. **Sign up** with any email NOT in `ADMIN_EMAILS`
2. **File a Request**: You'll be redirected to the request form
3. **Track Requests**: View your submitted requests at `/requests`
4. **Check Status**: See AI responses and admin decisions

## Troubleshooting

### "Phone number is required" error
✅ **Fixed!** This issue has been resolved. All form fields now properly submit to the backend.

### Not redirected to admin panel
- Verify your email is in `.env` under `ADMIN_EMAILS`
- Restart Docker Compose after editing `.env`
- Try logging out and logging back in

### Backend errors
- Check Docker logs: `docker compose logs backend`
- Ensure `ANTHROPIC_API_KEY` is set (or leave empty for stub responses)
- Verify `JWT_SECRET_KEY` is configured

### Frontend not loading
- Check Docker logs: `docker compose logs frontend`
- Ensure port 5173 is not in use
- Try rebuilding: `docker compose up --build`

## Next Steps

- Read [ADMIN_SETUP.md](./ADMIN_SETUP.md) for detailed admin configuration
- Read [CHANGES.md](./CHANGES.md) for technical details about recent fixes
- Check [README.md](./README.md) for full API reference and architecture details

## Running Tests

```bash
# From the backend directory
cd backend
python -m pytest

# Or using Docker
docker exec rti4all-backend pytest
```

## Stopping the Application

```bash
docker compose down
```

To also remove volumes:
```bash
docker compose down -v
```
