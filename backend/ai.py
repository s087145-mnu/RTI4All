"""
AI answer step for RTI requests.

Calls Claude Haiku 4.5 via the Anthropic SDK, grounding the response in
snippets pulled from a DataSource. Falls back to a stub answer if the API
key is missing so the demo still runs offline.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from data_source import DataSource

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"
_MAX_TOKENS = 1024

_SYSTEM_PROMPT = (
    "You are an assistant for a citizen Right to Information (RTI) portal. "
    "Given a citizen's RTI request and a set of source materials (prior "
    "responded requests in the same department, and general RTI FAQs), draft "
    "a clear, factual response addressed to the citizen.\n\n"
    "Rules:\n"
    "- Ground your answer in the provided sources. If the sources do not "
    "contain the specific information requested, say so plainly and point the "
    "citizen to the relevant department or next step.\n"
    "- Be concise: 4-8 sentences, plain prose, no markdown headings.\n"
    "- Do not invent figures, dates, names, or document references.\n"
    "- Cite prior requests only when directly relevant."
)


def _format_sources(sources: list[dict]) -> str:
    if not sources:
        return "(no source materials available)"
    lines: list[str] = []
    for i, s in enumerate(sources, start=1):
        if s.get("kind") == "prior_request":
            lines.append(
                f"[{i}] Prior request — Subject: {s['subject']}\n"
                f"    Description: {s['description']}\n"
                f"    Response: {s['response']}"
            )
        elif s.get("kind") == "faq":
            lines.append(f"[{i}] FAQ — Q: {s['question']}\n    A: {s['answer']}")
        else:
            lines.append(f"[{i}] {json.dumps(s, ensure_ascii=False)}")
    return "\n\n".join(lines)


def answer_request(
    *,
    department: str,
    subject: str,
    description: str,
    data_source: DataSource,
    department_id: str,
) -> str:
    """
    Generate a citizen-facing response for an RTI request.

    Raises RuntimeError if the Anthropic SDK call fails. Returns a stub
    string (clearly labelled) if ANTHROPIC_API_KEY is not configured.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set; returning stub response.")
        return (
            "[AI service not configured: set ANTHROPIC_API_KEY] "
            f"Your request to the {department} department has been received "
            "and is pending review."
        )

    sources = data_source.fetch(department_id=department_id, query=f"{subject} {description}")
    sources_block = _format_sources(sources)

    user_prompt = (
        f"Department: {department}\n"
        f"Subject: {subject}\n"
        f"Description: {description}\n\n"
        f"Source materials:\n{sources_block}\n\n"
        "Draft the response to the citizen now."
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    for block in message.content:
        if block.type == "text":
            return block.text.strip()

    raise RuntimeError("Anthropic response contained no text block.")
