# Structured Request Processing & Clarification Workflow

## Overview

The RTI4All system now features **intelligent request processing** with a **structured officer review workflow** and a **clarification feedback loop** between citizens and officers.

## Key Features

### 1. Structured Request Processing 🧠

When a citizen submits an RTI request, the AI automatically analyzes and structures it:

**Extracted Information:**
- **Request Type**: Data Request, Policy Clarification, Document Access, etc.
- **Key Questions**: 2-4 main questions being asked
- **Information Sought**: Specific data/documents requested
- **Time Period**: Any temporal scope mentioned (e.g., "2023", "Q1 2024")
- **Geographic Scope**: Location specified (e.g., "Baa Atoll", "All atolls")
- **Urgency Indicators**: Time-sensitive aspects

**Analysis Provided:**
- **Completeness Score** (0-1): How complete and clear the request is
- **Missing Information**: What would make the request clearer
- **Related Policies**: Relevant laws (e.g., RTI Act provisions)
- **Estimated Complexity**: Simple, Moderate, or Complex
- **Suggested Response Approach**: Guidance for the officer
- **Relevant Precedents**: Similar past requests

### 2. Officer Review Workflow 👮

Officers receive requests with structured data to help them:

**View Structured Analysis:**
```json
{
  "request_type": "Data Request",
  "key_questions": [
    "What is the vaccination coverage in each atoll?",
    "Are age-group breakdowns available?"
  ],
  "information_sought": [
    "COVID-19 vaccination coverage rates by atoll",
    "Age group breakdown for December 2023"
  ],
  "time_period": "December 2023",
  "geographic_scope": "All atolls",
  "completeness_score": 0.85,
  "missing_information": [],
  "estimated_complexity": "Moderate",
  "suggested_response_approach": "Check HPA quarterly reports. Verify if age breakdowns for smaller atolls can be released without privacy concerns."
}
```

**Officer Actions:**
1. **Approve** - If structured data and draft response are satisfactory
2. **Request Clarification** - If more information is needed from citizen
3. **Reject** - If request cannot be fulfilled (with explanation)

### 3. Clarification Feedback Loop 🔄

If the officer needs more information, they can request clarification:

**Officer Requests Clarification:**
```json
{
  "message": "Please provide more details to help us respond accurately.",
  "missing_fields": ["time_period", "geographic_scope"],
  "questions": [
    "Which specific atolls are you interested in?",
    "Do you need data for a specific time period?"
  ],
  "suggested_improvements": [
    "Specify whether you need first dose, second dose, or booster coverage",
    "Indicate if you need facility-level detail or atoll-level aggregate"
  ]
}
```

**Status Changes:**
- Request status → `"Clarification Needed"`
- Citizen receives notification with officer's questions
- Citizen can view the clarification request in their dashboard

**Citizen Responds:**
```json
{
  "updated_description": "I request COVID-19 vaccination coverage...",
  "additional_information": "I specifically need data for Male' and Addu City...",
  "answers_to_questions": {
    "Which specific atolls?": "Male' and Addu City",
    "Time period?": "December 2023"
  }
}
```

**After Citizen Update:**
- Request is **re-processed** with AI to extract new structured data
- Status changes back to `"Under Review"`
- Officer reviews updated request with improved completeness score
- Loop continues until officer is satisfied or approves response

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CITIZEN SUBMITS REQUEST                                  │
│    - Subject: "Vaccination Data"                            │
│    - Description: "I need vaccination stats"                │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. AI STRUCTURES REQUEST                                    │
│    - Extracts: key questions, data sought, time period      │
│    - Analyzes: completeness (0.6), complexity (Moderate)    │
│    - Identifies missing: geographic scope, specific metrics │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. OFFICER REVIEWS STRUCTURED DATA                          │
│    Status: "Under Review"                                   │
│    Completeness: 60%                                        │
│    Missing: geographic scope, time period                   │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. OFFICER REQUESTS CLARIFICATION                           │
│    "Please specify which atolls and time period"            │
│    Status → "Clarification Needed"                          │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. CITIZEN UPDATES REQUEST                                  │
│    Updated description: "...Male' and Addu City, Dec 2023"  │
│    Answers: { "Time period?": "December 2023" }             │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. AI RE-PROCESSES REQUEST                                  │
│    New completeness: 0.9                                    │
│    Status → "Under Review"                                  │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. OFFICER APPROVES                                         │
│    Reviews improved structured data                         │
│    Approves AI-drafted response (or edits)                  │
│    Status → "Responded"                                     │
│    ✅ LOOP ENDS - Citizen receives response                 │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Create Request (with Structured Processing)

**POST** `/api/requests`

```json
{
  "department_id": "moh",
  "subject": "Vaccination coverage by atoll",
  "description": "I need COVID-19 vaccination statistics..."
}
```

**Response includes:**
```json
{
  "id": "RTI-2024-0019",
  "status": "Under Review",
  "processed_data": {
    "completeness_score": 0.85,
    "key_questions": [...],
    "missing_information": [...],
    ...
  },
  ...
}
```

### Officer Requests Clarification

**PATCH** `/api/admin/requests/{request_id}`

```json
{
  "request_clarification": {
    "message": "Please provide more specific details",
    "missing_fields": ["time_period"],
    "questions": ["Which months do you need data for?"],
    "suggested_improvements": ["Specify atoll(s) of interest"]
  }
}
```

**Effect:**
- Status → `"Clarification Needed"`
- Citizen can see the clarification request
- Citizen dashboard shows action needed

### Citizen Updates Request

**PATCH** `/api/requests/{request_id}/clarify`

```json
{
  "updated_description": "Full updated request text...",
  "additional_information": "Additional context...",
  "answers_to_questions": {
    "Which months?": "January to December 2023"
  }
}
```

**Effect:**
- Status → `"Under Review"`
- Request is re-processed by AI
- New completeness score calculated
- Officer receives updated structured data

## Benefits

### For Officers 👮

1. **Organized Information**: Structured data makes review faster
2. **Completeness Assessment**: Know immediately if request needs clarification
3. **Guided Response**: AI suggests approach based on complexity
4. **Historical Context**: See relevant precedents
5. **Efficient Clarification**: Send structured requests instead of freeform emails

### For Citizens 👤

1. **Clear Feedback**: Know exactly what additional info is needed
2. **Guided Improvements**: Specific questions and suggestions
3. **Transparent Process**: See how request is being analyzed
4. **Faster Resolution**: Provide clarifications without re-filing

### For the System 🤖

1. **Quality Control**: Only complete requests generate AI drafts
2. **Continuous Learning**: Each clarification loop improves future requests
3. **Reduced Back-and-Forth**: Structured questions reduce email exchanges
4. **Better Data**: History of clarifications helps train AI

## Configuration

### Completeness Threshold

In `main.py`, requests must score ≥0.7 to generate AI draft automatically:

```python
if processed_data and processed_data.get("completeness_score", 0) >= 0.7:
    # Generate AI draft
    answer, request_status = _generate_answer(...)
else:
    # Wait for officer review
    request_status = "Under Review"
```

**Adjust this threshold** based on your needs:
- **Higher (0.8-0.9)**: More officer oversight, fewer automatic drafts
- **Lower (0.5-0.6)**: More automation, but drafts may be less accurate

## Example Scenarios

### Scenario 1: Complete Request (No Clarification Needed)

**Citizen Request:**
> Subject: "School infrastructure budget 2024"  
> Description: "Please provide the capital budget allocated for school infrastructure upgrades in Baa Atoll for fiscal year 2024, broken down by project type."

**AI Processing:**
- Completeness: 0.95
- Request type: Budget Information
- Geographic scope: Baa Atoll
- Time period: 2024
- Missing: None

**Outcome:**
- AI generates draft response immediately
- Status: "Under Review" (officer can approve/edit)
- No clarification needed

### Scenario 2: Incomplete Request (Clarification Needed)

**Citizen Request:**
> Subject: "Health statistics"  
> Description: "I need health data"

**AI Processing:**
- Completeness: 0.3
- Missing: specific metrics, time period, geographic scope

**Officer Action:**
```json
{
  "message": "Your request needs more specific details",
  "questions": [
    "What specific health metrics do you need (e.g., mortality rates, disease prevalence)?",
    "Which time period are you interested in?",
    "Do you need data for specific atolls or nationwide?"
  ],
  "suggested_improvements": [
    "Specify the type of health data (maternal health, communicable diseases, etc.)",
    "Include the year or date range"
  ]
}
```

**Citizen Update:**
> Updated Description: "I request maternal mortality rates for all atolls for the period 2020-2023, including causes where available."

**Re-processing:**
- New completeness: 0.88
- AI generates draft response
- Officer reviews and approves

### Scenario 3: Multiple Clarification Rounds

1. **Initial Request**: Vague → Clarification requested
2. **Update 1**: Partially improved → Another clarification
3. **Update 2**: Complete → Officer approves

**Clarification History** preserved:
```json
{
  "clarification_history": [
    {
      "timestamp": "2024-03-20",
      "requested_by": "officer@gov.mv",
      "clarification": { "message": "...", "questions": [...] }
    },
    {
      "timestamp": "2024-03-22",
      "requested_by": "officer@gov.mv",
      "clarification": { "message": "...", "questions": [...] }
    }
  ],
  "citizen_updates": [
    {
      "timestamp": "2024-03-21",
      "updated_description": "...",
      "answers_to_questions": {...}
    },
    {
      "timestamp": "2024-03-23",
      "updated_description": "...",
      "answers_to_questions": {...}
    }
  ]
}
```

## Monitoring & Analytics

### Track Clarification Metrics

```bash
# Count requests needing clarification
cat backend/data/sample_data.json | jq '[.requests[] | select(.status == "Clarification Needed")] | length'

# Average completeness score
cat backend/data/sample_data.json | jq '[.requests[].processed_data.completeness_score] | add / length'

# Requests by complexity
cat backend/data/sample_data.json | jq '[.requests[].processed_data.estimated_complexity] | group_by(.) | map({complexity: .[0], count: length})'
```

### Review Clarification History

```bash
# Requests with clarification history
cat backend/data/sample_data.json | jq '.requests[] | select(.clarification_history | length > 0) | {id, clarifications: (.clarification_history | length)}'
```

## Best Practices

### For Officers

1. **Be Specific**: Ask clear, focused questions
2. **Provide Examples**: Show what good requests look like
3. **Use Structured Fields**: Fill out all clarification fields properly
4. **Review Structured Data**: Trust but verify the AI analysis

### For Citizens

1. **Be Detailed**: Provide specific information upfront
2. **Include Context**: Time periods, locations, specific metrics
3. **Respond Fully**: Answer all questions in clarification requests
4. **Use Existing Data**: Reference what's already published

## Future Enhancements

1. **Auto-suggestions**: AI suggests improvements before submission
2. **Template Requests**: Pre-filled templates for common request types
3. **Smart Defaults**: Learn from user's past requests
4. **Notification System**: Email/SMS when clarification is requested
5. **Analytics Dashboard**: Track average completeness by department
6. **Multi-language**: Support Dhivehi language requests

## Support

For issues with structured processing:
1. Check `backend/request_processor.py` for AI processing logic
2. Review logs: `docker compose logs backend | grep "Processing new request"`
3. Test with sample requests of varying completeness
4. Adjust completeness threshold if needed

**The structured processing workflow ensures high-quality requests reach officers and provides a clear feedback loop for continuous improvement!** 🎯
