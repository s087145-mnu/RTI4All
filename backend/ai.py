"""
AI answer step for the Ministry of Climate Change, Environment and Energy
(Maldives) RTI portal.

Combines two grounding sources:

    1. RAG over the ministry's local archive — past responded RTI requests +
       FAQs. Retrieved items are injected into the system prompt as a
       "Ministry archive" block.
    2. Live web search and fetch via Claude's server-side tools, restricted
       to rtidhonbe.com (preferred) and environment.gov.mv (fallback).

The model gets ministry precedent (RAG) plus current facts (web) and is
instructed to ground every claim in one of them.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import anthropic

from rag import RAGIndex, format_retrieved_for_prompt

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"
_MAX_TOKENS = 2048
_MAX_PAUSE_TURNS = 3

_SYSTEM_PROMPT_TEMPLATE = (
    "You are an AI assistant for the Maldives Ministry of Climate Change, "
    "Environment and Energy's citizen Right to Information (RTI) portal.\n\n"
    "When a citizen submits an RTI request, your job is to draft a clear, "
    "factual response addressed to the citizen, grounded in two sources:\n\n"
    "A. THE MINISTRY ARCHIVE — past responded RTI requests and standing FAQs, "
    "   retrieved for you and shown below. These are authoritative precedent "
    "   and process knowledge. PREFER them when they answer the question.\n\n"
    "B. LIVE OFFICIAL SOURCES — accessible via the web_search and web_fetch "
    "   tools, restricted to:\n"
    "     1. rtidhonbe.com (the RTI vault) — search this FIRST.\n"
    "     2. environment.gov.mv (the ministry site) — search this ONLY IF the "
    "        vault does not have what is needed.\n\n"
    "DECISION ORDER:\n"
    "1. If the archive items below directly answer the question, draft from "
    "   them and cite the prior RTI id (e.g. RTI-2024-0001) or FAQ id.\n"
    "2. Otherwise use the web tools, vault first then the ministry site.\n"
    "3. If neither has the answer, say so plainly and direct the citizen to "
    "   file a formal RTI application with the Information Officer.\n\n"
    "MINISTRY ARCHIVE:\n{archive_block}\n\n"
    "RULES:\n"
    "- Every factual claim must come from the archive or from content you "
    "  retrieved via web_search/web_fetch. Do not invent figures, names, "
    "  dates, or document references.\n"
    "- State which source(s) you used (archive precedent, FAQ, rtidhonbe.com, "
    "  or environment.gov.mv).\n"
    "- Address the citizen directly. Be concise: 4-8 sentences, plain prose, "
    "  no markdown headings.\n\n"
    "OUTPUT FORMAT:\n"
    "Your final text reply will be shown to the citizen verbatim. Do NOT include "
    "search narration (\"I'll search...\", \"Let me try...\", \"The search "
    "returned...\"). Do NOT include any preamble or signoff like \"Response to "
    "Citizen:\", \"Dear Citizen,\", or \"Best regards\". Output ONLY the body of "
    "the response, in plain prose, starting with the substantive answer."
)

_ALLOWED_DOMAINS = ["rtidhonbe.com", "environment.gov.mv"]

_TOOLS = [
    {
        "type": "web_search_20260209",
        "name": "web_search",
        "allowed_domains": _ALLOWED_DOMAINS,
        "max_uses": 6,
        # Haiku 4.5 does not support programmatic tool calling (the default
        # mode for the _20260209 web tools). "direct" invokes the tool the
        # classic way (Claude emits a tool_use block) and disables dynamic
        # result filtering.
        "allowed_callers": ["direct"],
    },
    {
        "type": "web_fetch_20260209",
        "name": "web_fetch",
        "allowed_domains": _ALLOWED_DOMAINS,
        "max_uses": 8,
        "allowed_callers": ["direct"],
    },
]


def answer_request(
    *,
    subject: str,
    description: str,
    rag_index: Optional[RAGIndex] = None,
    rag_k: int = 4,
) -> str:
    """
    Generate a citizen-facing response, grounded in the ministry archive (RAG)
    and live web sources. Raises RuntimeError on hard failures; returns a
    clearly-labelled stub if ANTHROPIC_API_KEY is unset.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set; returning stub response.")
        return (
            "[AI service not configured: set ANTHROPIC_API_KEY] "
            "Your request to the Ministry of Climate Change, Environment and "
            "Energy has been received and is pending review."
        )

    # RAG retrieval — pulls past responded RTIs + relevant FAQs as precedent.
    archive_hits: list[dict] = []
    if rag_index is not None:
        query = f"{subject}\n{description}".strip()
        archive_hits = rag_index.retrieve(query, k=rag_k)
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        archive_block=format_retrieved_for_prompt(archive_hits)
    )

    user_prompt = (
        f"Subject: {subject}\n"
        f"Description: {description}\n\n"
        "First check the ministry archive shown in your instructions. If the "
        "archive does not answer the question, look up rtidhonbe.com (then "
        "environment.gov.mv). Then draft the response to the citizen."
    )

    client = anthropic.Anthropic(api_key=api_key)
    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    for _ in range(_MAX_PAUSE_TURNS + 1):
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            tools=_TOOLS,
            messages=messages,
        )
        if message.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": message.content})
    else:
        raise RuntimeError("Web-tool loop did not converge within pause_turn cap.")

    # When server-side tools run, the model emits short text blocks between
    # tool calls ("I'll search the vault...", "Let me try again..."). Those
    # are planning narration, not the answer. Keep only text blocks that
    # appear AFTER the last tool-use block in the content array.
    last_tool_idx = -1
    for i, block in enumerate(message.content):
        if block.type in {"tool_use", "server_tool_use"}:
            last_tool_idx = i

    final_text_parts = [
        block.text.strip()
        for block in message.content[last_tool_idx + 1 :]
        if block.type == "text" and block.text.strip()
    ]
    if not final_text_parts:
        raise RuntimeError("Anthropic response contained no final text block.")
    return "\n\n".join(final_text_parts)
