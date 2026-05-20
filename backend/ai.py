"""
AI answer step for the Ministry of Climate Change, Environment and Energy
(Maldives) RTI portal.

Calls Claude Haiku 4.5 with the server-side web_search + web_fetch tools.
Allowed-domains list is restricted to two sources, queried in priority order
by the model under explicit system-prompt instruction:

    1. rtidhonbe.com         — the RTI vault (preferred source of truth)
    2. environment.gov.mv    — the ministry's official site (fallback)
"""

from __future__ import annotations

import logging
import os

import anthropic

log = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"
_MAX_TOKENS = 2048
_MAX_PAUSE_TURNS = 3

_SYSTEM_PROMPT = (
    "You are an AI assistant for the Maldives Ministry of Climate Change, "
    "Environment and Energy's citizen Right to Information (RTI) portal.\n\n"
    "When a citizen submits an RTI request, your job is to look up authoritative "
    "information from the official sources and draft a clear, factual response "
    "addressed to the citizen.\n\n"
    "SOURCE PRIORITY (strict ordering — do not skip step 1):\n"
    "1. FIRST, search rtidhonbe.com using the web_search tool. This is the RTI "
    "   vault and the preferred source. Use web_fetch to retrieve any promising "
    "   document pages found in search results.\n"
    "2. ONLY IF rtidhonbe.com does not contain the requested information, search "
    "   environment.gov.mv — the ministry's official site — using the same tools.\n"
    "3. If neither source contains the requested information, say so plainly and "
    "   tell the citizen the next step (e.g. file a formal RTI application with "
    "   the ministry's Information Officer).\n\n"
    "RULES:\n"
    "- Every factual claim in your response must come from content you retrieved "
    "  via web_search or web_fetch. Do not invent figures, names, dates, or "
    "  document references.\n"
    "- State which source you used (rtidhonbe.com vs environment.gov.mv). If you "
    "  fell back to the ministry site, briefly note that the vault did not have "
    "  the requested information.\n"
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


def answer_request(*, subject: str, description: str) -> str:
    """
    Generate a citizen-facing response, sourced live from the two configured
    government websites. Raises RuntimeError on hard failures; returns a
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

    user_prompt = (
        f"Subject: {subject}\n"
        f"Description: {description}\n\n"
        "Look up the requested information on rtidhonbe.com first; only fall "
        "back to environment.gov.mv if the vault does not have it. Then draft "
        "the response to the citizen."
    )

    client = anthropic.Anthropic(api_key=api_key)
    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    for _ in range(_MAX_PAUSE_TURNS + 1):
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
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
