# AI Processing Not Working - Troubleshooting Guide

## Issue
Submitted RTI requests are not being processed by the AI. The request gets created but the status shows "Pending" instead of "Under Review" with an AI-generated draft response.

## Root Cause
The Anthropic API key is not configured properly. The backend shows this error:

```
anthropic.AuthenticationError: Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error', 'message': 'invalid x-api-key'}}
```

## Solution

### Step 1: Get an Anthropic API Key

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to "API Keys" section
4. Create a new API key
5. Copy the key (starts with `sk-ant-`)

### Step 2: Update the .env File

Edit your `.env` file and replace the placeholder:

**Before:**
```bash
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

**After:**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

### Step 3: Restart the Backend

The backend needs to be restarted to load the new environment variable:

```bash
docker compose restart backend
```

Or restart everything:
```bash
docker compose down
docker compose up
```

### Step 4: Verify It's Working

Check that the API key is loaded:

```bash
docker exec rti4all-backend printenv | grep ANTHROPIC_API_KEY
```

You should see your actual API key (starting with `sk-ant-`), not the placeholder.

## Testing

### Submit a Test Request

1. Log in to the application
2. Go to "File RTI" (http://localhost:5173/requests/new)
3. Fill in the form:
   - **Department**: Ministry of Climate Change, Environment and Energy
   - **Subject**: "Climate adaptation programs"
   - **Description**: "What climate adaptation programs are currently active?"
4. Submit

### Check the Result

1. Go to "Requests" page
2. Look at your request - the status should be **"Under Review"** (not "Pending")
3. Click on the request to see details
4. The "Response" section should show an AI-generated draft

### If Still Not Working

Check the backend logs:

```bash
docker compose logs backend --tail 100
```

Look for errors related to:
- `anthropic` - API errors
- `AI answer step failed` - Processing errors
- `invalid x-api-key` - Authentication errors

## How It Works

When a request is submitted, the backend:

1. **Checks the cache** - If the exact same question was asked before, reuse the answer
2. **Calls the AI** - Uses Anthropic's Claude API with:
   - RAG retrieval (searches past requests and FAQs)
   - Graph retrieval (finds related entities)
   - Web search tools (searches rtidhonbe.com and environment.gov.mv)
3. **Sets status**:
   - `"Under Review"` - AI successfully generated a draft
   - `"Pending"` - AI failed, needs manual review

## Fallback Behavior

If the API key is not set or invalid:
- Requests are created with status `"Pending"`
- The response field contains a stub message:
  ```
  [AI service not configured: set ANTHROPIC_API_KEY] 
  Your request has been received and is pending review.
  ```
- An admin can still manually add a response via the admin panel

## Alternative: Run Without AI

If you don't have an Anthropic API key:

1. Leave `ANTHROPIC_API_KEY` empty or with the placeholder
2. Requests will be filed as "Pending"
3. Admins can manually respond via the admin panel at `/admin`

This is useful for:
- Testing the application without API costs
- Development environments
- Scenarios where manual review is preferred

## Cost Considerations

Each AI-processed request uses:
- **Model**: Claude Haiku 4.5
- **Approximate cost**: ~$0.001-0.005 per request
- **Factors**: Query complexity, RAG results, web searches needed

The cache helps reduce costs - identical queries reuse the previous response.

## Security Note

⚠️ **Never commit your `.env` file to version control!**

The `.gitignore` already protects it, but double-check:
```bash
git status
```

If `.env` appears, it should NOT be staged. If it is:
```bash
git reset .env
```

Always use `.env.example` for sharing configuration templates.
