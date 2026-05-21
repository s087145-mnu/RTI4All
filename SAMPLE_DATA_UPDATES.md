# Sample Data with Structured Processing & Clarification Examples

## Overview

The sample data has been updated to include **structured processing data** and **clarification workflow examples**, demonstrating the complete feature set in action.

## What's Included

### Total Requests: 20 (up from 18)

**By Status:**
- Responded: 10
- Under Review: 3
- In Progress: 3
- Pending: 3
- **Clarification Needed: 1** ✨ NEW status

### Featured Examples

#### 1. **Complete Request (High Completeness Score)**
**RTI-2024-0001** - Coral reef bleaching data
- ✅ Completeness score: 0.92
- ✅ All required fields present
- ✅ AI generated draft response
- ✅ Officer approved
- **Shows**: Ideal request that flows smoothly through the system

**RTI-2024-0007** - COVID-19 vaccination statistics  
- ✅ Completeness score: 0.88
- ✅ Clear time period and geographic scope
- ✅ Specific metrics requested
- **Shows**: Well-structured request with clear parameters

#### 2. **Clarification Workflow (Complete Cycle)**
**RTI-2024-0019** - Healthcare facility statistics ⭐ FEATURED
- **Initial submission**: Vague request (completeness: 0.45)
- **Officer action**: Sent structured clarification with 4 specific questions
- **Citizen response**: Updated with detailed specifications
- **Outcome**: Request clarified and responded to
- **Shows**: Complete clarification cycle from start to finish

**Flow:**
```
1. Initial: "healthcare facilities...patient treatment data...across regions"
   → Score: 0.45 (too vague)

2. Officer clarification: 
   - "Which specific metrics?"
   - "Which region/facility?"
   - "What type of treatment data?"
   - "Facility-level or aggregates?"

3. Citizen update: 
   - "Addu City regional hospital"
   - "Daily patient load, bed occupancy, staffing ratios"
   - "Annual totals"

4. Response: Specific data provided for Addu City hospital
```

#### 3. **Awaiting Clarification (Active)**
**RTI-2024-0020** - Education data ✨ NEW
- **Status**: "Clarification Needed" (awaiting citizen response)
- **Completeness**: 0.15 (very incomplete)
- **Issue**: Too vague ("I need information about schools and education")
- **Officer clarification**: 4 detailed questions with examples
- **Shows**: Current active clarification request

#### 4. **Structured Data Examples**

All major requests now include `processed_data`:

```json
{
  "processed_data": {
    "request_type": "Data Request",
    "key_questions": [...],
    "information_sought": [...],
    "time_period": "2023",
    "geographic_scope": "Baa Atoll",
    "completeness_score": 0.88,
    "missing_information": [],
    "estimated_complexity": "Moderate",
    "suggested_response_approach": "...",
    "relevant_precedents": [...]
  }
}
```

## Completeness Score Distribution

| Score Range | Count | Example |
|-------------|-------|---------|
| 0.9 - 1.0 | 1 | RTI-2024-0001 (0.92) - Coral reef data |
| 0.8 - 0.9 | 2 | RTI-2024-0007 (0.88) - Vaccination stats |
| 0.7 - 0.8 | 0 | - |
| 0.4 - 0.7 | 1 | RTI-2024-0019 (0.45) - Healthcare (before clarification) |
| 0.0 - 0.4 | 1 | RTI-2024-0020 (0.15) - Education (very vague) |

## Clarification History Examples

### RTI-2024-0019 (Completed Cycle)
```json
{
  "clarification_history": [
    {
      "timestamp": "2024-03-12",
      "requested_by": "officer@gov.mv",
      "clarification": {
        "message": "...",
        "questions": [
          "Which specific healthcare metrics?",
          "Which region/facility?",
          "What type of treatment data?",
          "Facility-level or aggregates?"
        ]
      }
    }
  ],
  "citizen_updates": [
    {
      "timestamp": "2024-03-14",
      "updated_description": "...Addu City regional hospital...",
      "answers_to_questions": {
        "Which specific healthcare metrics?": "Patient load, bed occupancy...",
        "Which region?": "Addu City regional hospital"
      }
    }
  ]
}
```

### RTI-2024-0020 (Awaiting Response)
```json
{
  "status": "Clarification Needed",
  "clarification_requested": {
    "message": "Your request is quite broad...",
    "missing_fields": ["data_type", "geographic_scope", "time_period"],
    "questions": [
      "What specific education data?",
      "Which geographic area?",
      "What time period?",
      "Which education level?"
    ],
    "suggested_improvements": [
      "Be specific about the type of data",
      "Specify location",
      "Include timeframe",
      "Example: 'Student enrollment numbers for all primary schools in Thaa Atoll for 2023'"
    ]
  }
}
```

## Testing the Workflow

### View Structured Data
```bash
# See processed data for a request
cat backend/data/sample_data.json | jq '.requests[] | select(.id == "RTI-2024-0001") | .processed_data'

# View completeness scores
cat backend/data/sample_data.json | jq '.requests[] | {id, subject, completeness: .processed_data.completeness_score}'
```

### Check Clarification Examples
```bash
# Find requests with clarification history
cat backend/data/sample_data.json | jq '.requests[] | select(.clarification_history | length > 0) | {id, subject, clarifications: (.clarification_history | length)}'

# View active clarification requests
cat backend/data/sample_data.json | jq '.requests[] | select(.status == "Clarification Needed") | {id, subject, questions: .clarification_requested.questions}'
```

### Analyze Request Quality
```bash
# Average completeness by department
cat backend/data/sample_data.json | jq '[.requests[] | select(.processed_data) | {dept: .department_id, score: .processed_data.completeness_score}] | group_by(.dept) | map({department: .[0].dept, avg_completeness: (map(.score) | add / length | floor * 100 / 100)})'

# Requests by complexity
cat backend/data/sample_data.json | jq '[.requests[] | select(.processed_data) | .processed_data.estimated_complexity] | group_by(.) | map({complexity: .[0], count: length})'
```

## Key Fields Added

All requests now include:
- ✅ `processed_data` - Structured analysis (where applicable)
- ✅ `clarification_requested` - Current clarification (if any)
- ✅ `clarification_history` - All past clarifications
- ✅ `citizen_updates` - All citizen responses

## Data Persistence

All this data **persists automatically**:
- New requests get `processed_data` on creation
- Clarifications are saved to `clarification_history`
- Citizen updates are saved to `citizen_updates`
- Complete audit trail maintained

## Demo Scenarios

### Scenario 1: View High-Quality Request
```
Login → View RTI-2024-0001
→ See completeness score: 0.92
→ Review structured analysis
→ See AI-generated response
→ Shows ideal workflow
```

### Scenario 2: Review Clarification Cycle
```
Login → View RTI-2024-0019
→ See initial low score: 0.45
→ Read officer's clarification questions
→ Review citizen's detailed response
→ See how completeness improved
→ Shows successful clarification
```

### Scenario 3: Handle Active Clarification
```
Login as Officer → View RTI-2024-0020
→ See status: "Clarification Needed"
→ Review very low score: 0.15
→ Read officer's questions
→ Citizen can update via API
→ Shows current workflow state
```

## Benefits for Demo

1. **Real Examples**: Actual structured data, not placeholders
2. **Complete Workflow**: Shows entire clarification cycle
3. **Variety**: Different completeness scores and scenarios
4. **Active State**: One request awaiting clarification (realistic)
5. **Audit Trail**: Complete history preserved
6. **Persistence**: All data survives restarts

## Quick Stats

```bash
# Total requests with structured data
cat backend/data/sample_data.json | jq '[.requests[] | select(.processed_data)] | length'
# Output: 4 (featured examples)

# Requests with clarification history
cat backend/data/sample_data.json | jq '[.requests[] | select(.clarification_history | length > 0)] | length'
# Output: 2 (one complete, one active)

# Average completeness (where available)
cat backend/data/sample_data.json | jq '[.requests[] | select(.processed_data) | .processed_data.completeness_score] | add / length'
# Output: ~0.60 (realistic mix)
```

## Next Steps

The sample data now demonstrates:
✅ High-quality requests (0.9+ score)  
✅ Medium-quality requests (0.4-0.7 score)  
✅ Low-quality requests (< 0.4 score)  
✅ Complete clarification workflow  
✅ Active clarification state  
✅ Structured processing output  
✅ Audit trail preservation  

**The data now tells a complete story of the structured processing and clarification workflow!** 🎉
