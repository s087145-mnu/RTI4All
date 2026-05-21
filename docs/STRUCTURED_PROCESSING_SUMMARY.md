# 🎯 Structured Processing & Clarification Workflow - Summary

## What Was Added

The RTI4All system now features an intelligent **structured request processing** system with a **two-way clarification workflow** between citizens and officers.

## Key Components

### 1. **AI Request Analyzer** (`backend/request_processor.py`)
Automatically analyzes every submitted request to extract:
- Request type, key questions, information sought
- Time period, geographic scope, urgency indicators
- **Completeness score (0-1)** - How clear/complete the request is
- Missing information that would improve the request
- Complexity estimate (Simple/Moderate/Complex)
- Suggested response approach for the officer

### 2. **Officer Review With Structured Data**
Officers now see:
- ✅ Organized, structured analysis of each request
- ✅ Completeness assessment at a glance
- ✅ Clear list of what's missing (if anything)
- ✅ Complexity estimate to prioritize workload
- ✅ Suggested approach for responding

### 3. **Clarification Feedback Loop**
**NEW Workflow:**
```
Citizen → Submits Request → AI Structures It → Officer Reviews
                                                       ↓
                                           Need clarification?
                                                       ↓
                              Yes: Request Clarification ← No: Approve/Reject
                                         ↓
                        Status: "Clarification Needed"
                                         ↓
                 Citizen Updates with Answers
                                         ↓
                   AI Re-processes Request
                                         ↓
                    Back to Officer Review ✓
```

## New Statuses

- **"Clarification Needed"** - Officer has requested more info from citizen
- Officer can send structured clarification with:
  - Message explaining what's needed
  - Specific missing fields
  - List of questions for citizen
  - Suggested improvements

## New Endpoints

### `POST /api/requests`
- Now includes `processed_data` with structured analysis
- Only generates AI draft if completeness ≥ 0.7
- Otherwise waits for officer review

### `PATCH /api/admin/requests/{id}`
- New field: `request_clarification` for officers
- Sends structured clarification request to citizen
- Changes status to "Clarification Needed"

### `PATCH /api/requests/{id}/clarify` ✨ NEW
- Citizens use this to respond to clarification requests
- Provide updated description, additional info, answer questions
- Request is re-processed with improved completeness
- Status changes back to "Under Review"

## Files Added/Modified

### New Files
- `backend/request_processor.py` - AI request structuring (143 lines)
- `STRUCTURED_PROCESSING.md` - Complete documentation (415 lines)
- `STRUCTURED_PROCESSING_SUMMARY.md` - This file

### Modified Files
- `backend/main.py` - Integrated structured processing + clarification loop
  - Added `ProcessedRequestData`, `ClarificationRequest`, `CitizenUpdateRequest` models
  - Updated `create_request` to structure requests
  - Enhanced `admin_update_request` to handle clarifications
  - Added `citizen_update_request` endpoint
  - Added "Clarification Needed" status support

## Example Flow

### Complete Request (No Clarification)
```
1. Citizen: "Provide renewable energy capacity in Baa Atoll for 2024"
2. AI: Completeness 0.92 → Generates draft response
3. Officer: Reviews structured data → Approves
4. Done! ✅
```

### Incomplete Request (Needs Clarification)
```
1. Citizen: "I need some data about schools"
2. AI: Completeness 0.35 → No draft generated
3. Officer: Reviews → Requests clarification
   - "Which specific data? (enrollment, budget, infrastructure?)"
   - "Which atolls?"
   - "Which time period?"
4. Citizen: Updates request with specifics
5. AI: Re-processes → Completeness 0.85 → Generates draft
6. Officer: Reviews improved request → Approves
7. Done! ✅
```

## Benefits

### For Officers
- **Faster Review**: Structured data is easier to scan
- **Better Decisions**: Completeness score guides action
- **Efficient Clarifications**: Send structured questions instead of emails
- **Track History**: See all clarification rounds in one place

### For Citizens  
- **Clear Guidance**: Know exactly what to improve
- **Faster Resolution**: Provide clarifications without re-filing
- **Transparency**: See how AI analyzes their request
- **Learning**: Improve future requests based on feedback

### For the System
- **Quality Gate**: Incomplete requests don't generate poor AI drafts
- **Continuous Improvement**: Clarification history trains better prompts
- **Reduced Email**: Structured workflow replaces ad-hoc communication
- **Audit Trail**: Complete history of request evolution

## Configuration

### Completeness Threshold (main.py)
```python
if processed_data and processed_data.get("completeness_score", 0) >= 0.7:
    # Auto-generate AI draft
else:
    # Wait for officer review
```

**Adjust 0.7 threshold:**
- **Higher (0.8-0.9)**: More selective, more officer oversight
- **Lower (0.5-0.6)**: More automation, but may need more clarifications

## Quick Test

### Test Incomplete Request
```bash
curl -X POST http://localhost:8000/api/requests \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "department_id": "moh",
    "subject": "Health data",
    "description": "I need some statistics"
  }'
```

**Expected:**
- Completeness score low (~0.3-0.5)
- Status: "Under Review" (no AI draft)
- `missing_information` list populated

### Test Complete Request
```bash
curl -X POST http://localhost:8000/api/requests \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "department_id": "moh",
    "subject": "COVID-19 vaccination coverage",
    "description": "Please provide COVID-19 vaccination coverage rates for Male and Addu City for December 2023, broken down by age group if available."
  }'
```

**Expected:**
- Completeness score high (~0.85-0.95)
- Status: "Under Review" (with AI draft in `response`)
- `missing_information` empty or minimal

## Monitoring

```bash
# View structured processing logs
docker compose logs backend | grep "Processing new request"
docker compose logs backend | grep "completeness="

# Check requests awaiting clarification
cat backend/data/sample_data.json | jq '.requests[] | select(.status == "Clarification Needed")'

# Average completeness by department
cat backend/data/sample_data.json | jq '[.requests[] | {dept: .department_id, score: .processed_data.completeness_score}] | group_by(.dept) | map({dept: .[0].dept, avg: (map(.score) | add / length)})'
```

## Documentation

- **Full Guide**: `STRUCTURED_PROCESSING.md` - Complete workflow documentation
- **This Summary**: Quick reference for the feature
- **API Docs**: http://localhost:8000/docs (FastAPI auto-generated)

## What This Solves

✅ **Problem**: Officers receive vague requests and waste time asking for clarifications via email  
✅ **Solution**: AI structures requests and officers send structured clarification requests  

✅ **Problem**: Citizens don't know what information to provide  
✅ **Solution**: Clear questions and suggestions guide them  

✅ **Problem**: Multiple back-and-forth email threads are hard to track  
✅ **Solution**: All clarifications and updates stored in request history  

✅ **Problem**: Poor requests generate poor AI responses  
✅ **Solution**: Completeness gate ensures only good requests get AI drafts  

## Next Steps (Optional Enhancements)

1. **Email notifications** when clarification is requested
2. **Request templates** with pre-filled structured fields
3. **Smart suggestions** shown to citizen as they type
4. **Analytics dashboard** for average completeness by department
5. **Multi-round auto-clarification** where AI asks follow-up questions

**The system now has a professional, organized workflow that improves request quality and speeds up resolution!** 🎉
