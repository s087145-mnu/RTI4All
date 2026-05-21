"""
AI processing for RTI requests.

Analyzes citizen requests and generates structured data for officer review,
including completeness assessment, missing information identification, and
suggested response approaches.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import anthropic

log = logging.getLogger(__name__)


def process_request_structure(
    *,
    subject: str,
    description: str,
    department_id: str,
    anthropic_client: Optional[anthropic.Anthropic] = None,
) -> dict[str, Any]:
    """
    Process a citizen's RTI request into structured data for officer review.

    Args:
        subject: The request subject/title
        description: The detailed request description
        department_id: ID of the target department
        anthropic_client: Optional Anthropic client (uses env var if not provided)

    Returns:
        Dictionary containing structured analysis (ProcessedRequestData format)
    """
    if not anthropic_client:
        import os

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key.startswith("sk-ant-placeholder"):
            log.warning("No valid Anthropic API key, returning basic structure")
            return _create_fallback_structure(subject, description)
        anthropic_client = anthropic.Anthropic(api_key=api_key)

    # Type check to satisfy linter
    if anthropic_client is None:
        return _create_fallback_structure(subject, description)

    try:
        prompt = f"""You are an AI assistant helping process Right to Information (RTI) requests in the Maldives.

Analyze the following RTI request and provide a structured analysis in JSON format.

CITIZEN REQUEST:
Subject: {subject}
Description: {description}
Department: {department_id}

Provide your analysis as a JSON object with these fields:

1. "request_type": Classify as "Data Request", "Policy Clarification", "Document Access", "Budget Information", "Procedure Inquiry", or "Other"

2. "key_questions": List 2-4 main questions the citizen is asking

3. "information_sought": List specific data, documents, or information items requested

4. "time_period": Extract any time period mentioned (e.g., "2023", "Q1 2024", "January-December 2023") or null

5. "geographic_scope": Extract any geographic scope (e.g., "Baa Atoll", "Male'", "All atolls", "Northern region") or null

6. "urgency_indicators": List any time-sensitive aspects or urgency indicators (empty array if none)

7. "completeness_score": Rate 0.0 to 1.0 how complete and clear the request is

8. "missing_information": List what additional information would make this request clearer (empty array if complete)

9. "related_policies": List relevant Maldivian laws, policies, or RTI Act provisions (empty array if none obvious)

10. "estimated_complexity": Classify as "Simple" (straightforward data lookup), "Moderate" (requires some analysis/compilation), or "Complex" (extensive research or multiple sources)

11. "suggested_response_approach": Brief 2-3 sentence suggestion on how the officer should approach responding

12. "relevant_precedents": List any similar types of requests that might have been processed before (empty array if none)

Respond ONLY with the JSON object, no other text."""

        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text.strip()

        # Extract JSON from response (in case there's extra text)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        processed = json.loads(content)

        log.info(
            f"Successfully processed request structure: "
            f"completeness={processed.get('completeness_score', 0):.2f}, "
            f"complexity={processed.get('estimated_complexity', 'Unknown')}"
        )

        return processed

    except anthropic.APIError as e:
        log.error(f"Anthropic API error processing request: {e}", exc_info=True)
        return _create_fallback_structure(subject, description)
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse AI response as JSON: {e}", exc_info=True)
        return _create_fallback_structure(subject, description)
    except Exception as e:
        log.error(f"Unexpected error processing request structure: {e}", exc_info=True)
        return _create_fallback_structure(subject, description)


def _create_fallback_structure(subject: str, description: str) -> dict[str, Any]:
    """
    Create a basic fallback structure when AI processing fails.
    """
    return {
        "request_type": "Data Request",
        "key_questions": [subject],
        "information_sought": [
            description[:200] + "..." if len(description) > 200 else description
        ],
        "time_period": None,
        "geographic_scope": None,
        "urgency_indicators": [],
        "completeness_score": 0.6,
        "missing_information": [
            "Request requires officer review to determine needed clarifications"
        ],
        "related_policies": ["Right to Information Act (Act No. 1/2014)"],
        "estimated_complexity": "Moderate",
        "suggested_response_approach": "Review the request details and determine if all necessary information has been provided. Contact the citizen if clarification is needed.",
        "relevant_precedents": [],
    }
