# Quick Fix: AI Not Processing Requests

## Problem
✗ Requests show status "Pending" instead of "Under Review"  
✗ No AI-generated draft response  
✗ Backend logs show: `authentication_error: invalid x-api-key`

## Solution (3 steps)

### 1. Get API Key
Visit: https://console.anthropic.com/settings/keys  
Copy your API key (starts with `sk-ant-`)

### 2. Update `.env` File
```bash
# Edit RTI4All/.env
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-ACTUAL-KEY-HERE
```

### 3. Restart Backend
```bash
cd RTI4All
docker compose restart backend
```

## Verify It Works

**Check environment:**
```bash
docker exec rti4all-backend printenv | grep ANTHROPIC_API_KEY
```
Should show your real key, not `your-anthropic-api-key-here`

**Submit a test request:**
1. Login → File RTI
2. Submit any question
3. Check status → Should be "Under Review" (not "Pending")

## Still Not Working?

**View backend logs:**
```bash
docker compose logs backend --tail 50 | grep -i "anthropic\|error"
```

**Common issues:**
- ❌ API key still has placeholder value → Edit `.env` again
- ❌ Backend not restarted → Run `docker compose restart backend`
- ❌ Invalid API key → Get a new one from Anthropic console
- ❌ API key has wrong format → Should start with `sk-ant-`

## Working Without AI (Optional)

Don't have an API key? The system still works:
- Requests are filed as "Pending"
- Admins can manually respond via `/admin`
- Good for testing/development

---

**For detailed information, see:** [AI_TROUBLESHOOTING.md](./AI_TROUBLESHOOTING.md)
