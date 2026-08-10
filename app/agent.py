"""
Lead-agent demo — agent brain.

Provides a pluggable "agent" that turns an incoming customer message into an
appropriate reply for a phone-only local business (e.g. a plumber).

Two backends:
  * LLMBackend  — uses DeepSeek V4 Flash via OpenRouter (real AI replies)
  * RuleBackend — deterministic rule-based fallback (works offline, no key)

Both expose the same interface: `Agent.respond(lead, customer_msg) -> str`.

This is a DEMO. It simulates a "missed call → SMS textback → qualify → hand off"
flow without real Twilio/ClickSend. Real SMS/voice wiring is the client-dependent
step (requires a real AU number + provider account).

NOTE (AU): Australia uses SMS + phone, not WhatsApp. Handoff to the business owner
is via SMS summary + call-forwarding (phone-only client), NOT a Telegram/web ping.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Business profile (the demo client's facts the agent should know)
# --------------------------------------------------------------------------- #
BUSINESS_FACTS = {
    "name": "PlumbRight Plumbing",
    "owner": "Dan",
    "trade": "plumber",
    "service_area": "Brisbane (northside, inner suburbs)",
    "hours": "Mon–Fri 7am–6pm, Sat 8am–2pm, 24/7 emergency callouts",
    "pricing": {
        "callout_standard": "A$85 callout fee, waived if you proceed with the job",
        "callout_afterhours": "A$180 after-hours emergency callout",
        "typical_jobs": {
            "burst pipe": "from A$220",
            "hot water system": "from A$350 + unit",
            "blocked drain": "from A$180",
            "tap/leak": "from A$120",
        },
    },
    "emergency_advice": {
        "burst_pipe": (
            "If a pipe has burst, turn off the mains water valve (near the street "
            "meter or under the sink) to stop the flooding, then open a tap to "
            "drain the line."
        ),
        "hot_water_leak": (
            "For a hot water system leak, turn off the water valve on the tank and, "
            "if possible, the tap/valve feeding the unit. Switch off the power/gas "
            "to the unit for safety."
        ),
        "blocked_drain": "Avoid using the drain until inspected; stop running water into it.",
    },
    "booking_request": (
        "May I confirm your name and mobile number so we can schedule you? "
        "Standard callouts are booked within our business hours; emergency callouts "
        "arrive within 60–90 minutes."
    ),
}

QUALIFICATION_FIELDS = ["suburb", "issue", "urgency", "customer_name", "customer_mobile"]

# --------------------------------------------------------------------------- #
# Lead model
# --------------------------------------------------------------------------- #
@dataclass
class Lead:
    id: str
    customer_phone: str
    first_message: str = ""
    suburb: Optional[str] = None
    issue: Optional[str] = None
    urgency: Optional[str] = None
    customer_name: Optional[str] = None
    customer_mobile: Optional[str] = None
    status: str = "new"  # new -> qualifying -> qualified -> handed_off
    history: list = field(default_factory=list)
    handoff_sms: Optional[str] = None

    def add(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text})

    def is_qualified(self) -> bool:
        return all(
            getattr(self, f) is not None for f in QUALIFICATION_FIELDS
        )

    @property
    def qualified_summary(self) -> str:
        return (
            f"NEW LEAD — {BUSINESS_FACTS['name']}\n"
            f"• Name: {self.customer_name}, {self.suburb}\n"
            f"• Issue: {self.issue}\n"
            f"• Urgency: {self.urgency}\n"
            f"• Their #: {self.customer_mobile}\n"
            f"• Replied within ~2s of missed call"
        )


# --------------------------------------------------------------------------- #
# LLM backend (OpenRouter / DeepSeek V4 Flash)
# --------------------------------------------------------------------------- #
class LLMBackend:
    SYSTEM_PROMPT = (
        "You are the after-hours SMS assistant for a local Australian trade "
        "business. You reply to customers by TEXT MESSAGE, so be concise, warm, "
        "and practical — short sentences, friendly tone, occasional emoji. "
        "You do NOT hand out the owner's number; you qualify the lead and offer "
        "to book.\n\n"
        "BUSINESS FACTS:\n" + json.dumps(BUSINESS_FACTS, indent=2) + "\n\n"
        "FLOW:\n"
        "1. On first contact, acknowledge + give relevant emergency advice if the "
        "issue sounds urgent, and ask one qualifying question (suburb or issue).\n"
        "2. Ask for suburb, then issue, then urgency, then name + mobile.\n"
        "3. Once you have all of suburb/issue/urgency/name/phone, say you've booked "
        "them (respect business hours vs after-hours callout) and confirm you'll "
        "have the owner call/arrive. Do NOT continue asking from that point.\n"
        "Keep each reply under ~120 words. Only ask ONE question at a time."
    )

    def __init__(self, api_key: str, model: str = "deepseek/deepseek-v4-flash-0731"):
        self.api_key = api_key
        self.model = model
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def respond(self, lead: Lead, customer_msg: str) -> str:
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.append({
            "role": "system",
            "content": "CURRENTLY KNOWN FACTS (do NOT re-ask anything listed here):\n"
            + (json.dumps(
                {f: getattr(lead, f) for f in QUALIFICATION_FIELDS if getattr(lead, f) is not None},
                indent=2) or "{}"),
        })
        for row in lead.history:
            messages.append(row)
        messages.append({"role": "user", "content": customer_msg})

        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "max_tokens": 500,  # reasoning model burns tokens on [reasoning]; 200 left content=None
                "temperature": 0.4,
            }
        ).encode()

        req = urllib.request.Request(
            self.url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://paulbrugman.com/lead-agent/",
                "X-Title": "Lead-Agent Demo",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                content = data["choices"][0]["message"].get("content")
                if content and content.strip():
                    return content.strip()
                print(f"[LLMBackend] empty content from OpenRouter: {data}")
        except Exception as e:  # noqa: BLE001 — fall back on any failure
            print(f"[LLMBackend] OpenRouter call failed, falling back: {e}")
        return RuleBackend().respond(lead, customer_msg)


# --------------------------------------------------------------------------- #
# Rule backend (offline fallback + field extraction)
# --------------------------------------------------------------------------- #
class RuleBackend:
    FIELD_QUESTIONS = {
        "suburb": "Thanks for reaching us! 🙂 To help fast — which suburb are you in?",
        "issue": "Got it. And what's the issue — burst pipe, hot water, blocked drain, or a leak?",
        "urgency": "No problem. Is this an emergency needing after-hours help tonight, or can it wait until business hours?",
        "customer_name": "Great — may I grab your name and best mobile number so we can book you?",
        "customer_mobile": "And your best mobile number so we can reach you?",
    }

    def respond(self, lead: Lead, customer_msg: str) -> str:
        RuleBackend.extract(lead, customer_msg)

        if lead.is_qualified():
            lead.status = "qualified"
            return (
                f"Perfect, you're all booked {lead.customer_name}! ✅ "
                + self._booking_line(lead)
                + " We'll have Dan confirm with a quick call. Thanks for your patience!"
            )

        # ask next missing field, one at a time
        for field_name in QUALIFICATION_FIELDS:
            if getattr(lead, field_name) is None:
                return self.FIELD_QUESTIONS[field_name]
        return self.FIELD_QUESTIONS["name"]

    def _booking_line(self, lead: Lead) -> str:
        if lead.urgency and "tonight" in (lead.urgency or "").lower():
            return f"An emergency callout will arrive within 60–90 minutes (after-hours callout {BUSINESS_FACTS['pricing']['callout_afterhours']})."
        return "We'll schedule you within business hours (Mon–Fri 7am–6pm)."

    # ------------------------------------------------------------------ #
    # Field extraction (shared — runs for BOTH backends)
    # ------------------------------------------------------------------ #
    _NAME_STOPWORDS = {
        "in", "at", "from", "about", "a", "an", "the", "just", "calling",
        "ringing", "after", "for", "with", "on", "here", "there", "really",
        "currently", "now", "so", "having", "getting", "a", "my", "your",
    }
    # Broad Brisbane suburb list (north + south side). "Sunnybank Hills" was
    # missing here, which caused the 'stupid' re-ask regression.
    _SUBURBS = [
        # north / inner
        "new farm", "paddington", "fortitude valley", "bowen hills", "milton",
        "spring hill", "taringa", "toowong", "west end", "south brisbane",
        "kelvin grove", "wilston", "grange", "ashgrove", "bardon", "auchenflower",
        "red hill", "herston", "windsor", "lutwyche", "albion", "wooloowin",
        "clayfield", "ascot", "hamilton", "newstead", "teneriffe", "hendra",
        "nundah", "northgate", "virginia", "zillmere", "chermside",
        # south side
        "sunnybank", "sunnybank hills", "coorparoo", "mount gravatt", "mount gravatt east",
        "woolloongabba", "annerley", "holland park", "greenslopes", "highgate hill",
        "cannon hill", "stones corner", "carindale", "moorooka", "salisbury",
        "eight mile plains", "rocklea", "yeerongpilly", "tarragindi", "fairfield",
        "dutton park", "norman park", "east brisbane", "kangaroo point",
        "morningside", "bulimba", "hawthorne", "balmoral", "camp hill", "carina",
    ]
    _FIELD_PATTERNS = {
        "suburb": r"\b((?:%s)\b)" % "|".join(sorted(_SUBURBS, key=len, reverse=True)),
        "urgency": r"\b((?:tonight|now|asap|as soon as possible|emergency|urgent|tomorrow|this week|not urgent|can wait|asap)\b)",
        "customer_mobile": r"(\b0[45]\d{8}\b)",
        "customer_name": r"\b(?:my name(?:'s| is)|this is|called|i'?m)\s+([a-z]+)",
        "issue": r"\b((?:burst pipe|burst|hot water system|hot water|water heater|tank|leak|leaking|blocked drain|drain|toilet|tap|faucet|pump)\b)",
    }
    # Generic fallback: capture "in <suburb>" when not an already-known suburb.
    _SUBURB_FALLBACK = re.compile(r"\bin\s+([a-z]+(?:\s+[a-z]{2,})?)\b")

    @staticmethod
    def extract(lead: Lead, msg: str) -> None:
        low = msg.lower()
        if lead.suburb is None:
            m = re.search(RuleBackend._FIELD_PATTERNS["suburb"], low)
            if m:
                lead.suburb = " ".join(w.capitalize() for w in m.group(1).split())
            else:
                # last-ditch: "in <word>" that isn't a name/stopword
                m = RuleBackend._SUBURB_FALLBACK.search(low)
                if m:
                    cand = m.group(1)
                    if cand not in RuleBackend._NAME_STOPWORDS and not any(
                        tok in cand for tok in ("name", "mobile", "phone")
                    ):
                        lead.suburb = " ".join(w.capitalize() for w in cand.split())
        if lead.issue is None:
            m = re.search(RuleBackend._FIELD_PATTERNS["issue"], low)
            if m:
                lead.issue = m.group(1).title()
        if lead.urgency is None:
            m = re.search(RuleBackend._FIELD_PATTERNS["urgency"], low)
            if m:
                lead.urgency = m.group(1).title()
        if lead.customer_mobile is None:
            m = re.search(RuleBackend._FIELD_PATTERNS["customer_mobile"], low)
            if m:
                lead.customer_mobile = m.group(1)
        if lead.customer_name is None:
            m = re.search(RuleBackend._FIELD_PATTERNS["customer_name"], low)
            if m:
                candidate = m.group(1)
                if candidate not in RuleBackend._NAME_STOPWORDS:
                    lead.customer_name = candidate.capitalize()


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def make_agent() -> Agent:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    model = os.environ.get("LEAD_AGENT_MODEL", "deepseek/deepseek-v4-flash-0731").strip()
    if key:
        print(f"[agent] using LLM backend: {model}")
        return Agent(LLMBackend(key, model))
    print("[agent] no OPENROUTER_API_KEY, using rule backend")
    return Agent(RuleBackend())


class Agent:
    """Facade so callers don't care which backend is active."""

    def __init__(self, backend):
        self.backend = backend

    def initial_textback(self, lead: Lead) -> str:
        """Simulated 'missed call → auto SMS' first message."""
        RuleBackend.extract(lead, lead.first_message)
        return self.backend.respond(lead, lead.first_message)

    def respond(self, lead: Lead, customer_msg: str) -> str:
        RuleBackend.extract(lead, customer_msg)
        return self.backend.respond(lead, customer_msg)
