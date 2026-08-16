"""
Lead-agent demo — FastAPI app.

Endpoints:
  GET  /                -> chat demo UI
  POST /api/call        -> simulate a missed call (creates a lead, returns textback)
  POST /api/reply       -> customer replies (returns agent response; marks handoff when qualified)
  GET  /api/leads       -> JSON of all leads in this demo run
  GET  /api/health      -> liveness

Demo note: real SMS/voice (ClickSend/Twilio) and the client's phone line are
NOT wired here — that's the client-dependent step requiring a real AU number +
provider account. This simulates the full *flow*.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import time
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .agent import RuleBackend, make_agent, Lead

app = FastAPI(title="Lead-Agent Demo")
app.mount("/static", StaticFiles(directory="static"), name="static")

_agent = make_agent()
_LEADS: dict[str, Lead] = {}

# ---- Rate limiting (T2) --------------------------------------------------- #
# /api/call and /api/reply are PUBLIC POST endpoints that each trigger an LLM
# call (OpenRouter) — firing them in a tight loop burns real money / SMS spend.
# slowapi runs IN-APP so we limit ONLY those two routes (the UI, /static,
# /api/leads and /api/health are untouched), and it works behind the Traefik
# path-prefix router + Cloudflare Tunnel where all clients share one source IP
# (which would make edge-level per-client limiting unreliable).
#
# Keyed on the client IP. Tune per client via env; sensible demo defaults.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_CALL_LIMIT = os.environ.get("RATE_LIMIT_CALL", "10/minute").strip()
_REPLY_LIMIT = os.environ.get("RATE_LIMIT_REPLY", "30/minute").strip()

# Admin token for GET /api/leads (which exposes customer PII). Fail-closed: if
# no token is configured the endpoint is disabled. Set via env to enable.
_ADMIN_TOKEN = os.environ.get("LEADS_ADMIN_TOKEN", "").strip()

# ---- Input guards (T3 hardening) ------------------------------------------ #
# Cap a single customer message at ~3000 chars and the whole body at 64 KB —
# reject oversized payloads instead of silently truncating.
MAX_MESSAGE_CHARS = 3000
MAX_BODY_BYTES = 64 * 1024
DEFAULT_CUSTOMER_PHONE = "+614****0000"
DEFAULT_FIRST_MESSAGE = (
    "hi, my water heater is leaking and water is going everywhere. are you open?"
)
# Reuse the agent's existing AU-mobile regex (0[45] + 8 digits) for validation.
_MOBILE_RE = re.compile(RuleBackend._FIELD_PATTERNS["customer_mobile"])


async def _read_json(req: Request) -> tuple[Optional[dict], Optional[JSONResponse]]:
    """Parse a JSON request body; reject malformed / oversized bodies.

    Returns (body, None) on success or (None, error_response) on failure.
    """
    raw = await req.body()
    if len(raw) > MAX_BODY_BYTES:
        return None, JSONResponse(
            {"error": f"request body too large (max {MAX_BODY_BYTES} bytes)"},
            status_code=413,
        )
    try:
        return json.loads(raw.decode("utf-8")), None
    except Exception:  # noqa: BLE001 - malformed JSON / bad encoding
        return None, JSONResponse({"error": "invalid JSON body"}, status_code=400)


def _validate_customer_phone(phone: object) -> Optional[str]:
    """Validate an AU mobile for /api/call. Returns an error message or None.

    Accepts the demo masked placeholder or a real AU mobile (local like
    0412345678, or +61 412 345 678 international form).
    """
    if not isinstance(phone, str) or not phone.strip():
        return "customer_phone is required"
    p = phone.strip()
    if p == DEFAULT_CUSTOMER_PHONE:
        return None  # demo masked placeholder
    digits = re.sub(r"\D", "", p)
    if digits.startswith("61") and len(digits) == 11:
        digits = "0" + digits[2:]  # +61 412... -> 0412...
    if len(digits) != 10 or not re.fullmatch(_MOBILE_RE, digits):
        return "customer_phone must be a valid AU mobile (e.g. 0412345678)"
    return None


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _require_admin(
    x_admin_token: str | None = Header(None),
    authorization: str | None = Header(None),
) -> None:
    """Fail-closed gate for the PII-dumping /api/leads endpoint.

    Accepts `X-Admin-Token: <token>` or `Authorization: Bearer <token>`,
    compared in constant time. Any missing/mismatching token, or an unset
    environment variable, gets a 401.
    """
    token = x_admin_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="admin token required")
    if not _ADMIN_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="admin token not configured (set LEADS_ADMIN_TOKEN)",
        )
    if not hmac.compare_digest(token, _ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="invalid admin token")


def _ts() -> str:
    return time.strftime("%H:%M:%S")


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.post("/api/call")
@limiter.limit(_CALL_LIMIT)
async def simulate_call(request: Request):
    """Simulate a customer's missed call → create lead → return the textback."""
    body, err = await _read_json(request)
    if err:
        return err
    assert body is not None  # err is None -> body parsed successfully

    customer_phone = body.get("customer_phone", DEFAULT_CUSTOMER_PHONE)
    phone_err = _validate_customer_phone(customer_phone)
    if phone_err:
        return JSONResponse({"error": phone_err}, status_code=400)

    first_message = body.get("message", DEFAULT_FIRST_MESSAGE)
    if not isinstance(first_message, str):
        return JSONResponse({"error": "message must be a string"}, status_code=400)
    first_message = first_message.strip() or DEFAULT_FIRST_MESSAGE
    if len(first_message) > MAX_MESSAGE_CHARS:
        return JSONResponse(
            {"error": f"message too long (max {MAX_MESSAGE_CHARS} chars)"},
            status_code=400,
        )

    lead = Lead(id=_new_id(), customer_phone=customer_phone, first_message=first_message)
    lead.add("user", first_message)
    reply = _agent.initial_textback(lead)
    lead.add("assistant", reply)
    _LEADS[lead.id] = lead

    return {
        "lead_id": lead.id,
        "status": lead.status,
        "customer_message": first_message,
        "agent_reply": reply,
        "handoff": None,
    }


@app.post("/api/reply")
@limiter.limit(_REPLY_LIMIT)
async def customer_reply(request: Request):
    body, err = await _read_json(request)
    if err:
        return err
    assert body is not None  # err non-None -> body parsed successfully

    # Validate lead owns / exists BEFORE touching it (fail before any mutation).
    lead_id = body.get("lead_id")
    if not isinstance(lead_id, str) or not lead_id or lead_id not in _LEADS:
        return JSONResponse({"error": "unknown lead_id"}, status_code=404)

    message = body.get("message")
    if not isinstance(message, str):
        return JSONResponse({"error": "message must be a string"}, status_code=400)
    message = message.strip()
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)
    if len(message) > MAX_MESSAGE_CHARS:
        return JSONResponse(
            {"error": f"message too long (max {MAX_MESSAGE_CHARS} chars)"},
            status_code=400,
        )

    lead = _LEADS[lead_id]
    lead.add("user", message)
    reply = _agent.respond(lead, message)
    lead.add("assistant", reply)

    handoff = None
    if lead.is_qualified() and lead.status != "handed_off":
        lead.status = "handed_off"
        # Simulated SMS + call-forward to the phone-only owner (Dan)
        lead.handoff_sms = lead.qualified_summary + (
            f"\n• How handled: {'booked, owner to ' + ('call back' if lead.urgency and lead.urgency.lower().count('tonight') else 'confirm')}"
        )

    return {
        "lead_id": lead.id,
        "status": lead.status,
        "customer_message": message,
        "agent_reply": reply,
        "handoff": {"sms": lead.handoff_sms} if lead.handoff_sms else None,
    }


@app.get("/api/leads", dependencies=[Depends(_require_admin)])
async def list_leads():
    return [
        {
            "id": lead.id,
            "customer_phone": lead.customer_phone,
            "status": lead.status,
            "suburb": lead.suburb,
            "issue": lead.issue,
            "urgency": lead.urgency,
            "name": lead.customer_name,
            "mobile": lead.customer_mobile,
            "history": lead.history,
            "handoff_sms": lead.handoff_sms,
        }
        for lead in _LEADS.values()
    ]


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Chat UI
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    html = open("static/index.html", encoding="utf-8").read()
    root_path = request.scope.get("root_path", "") or ""
    return HTMLResponse(
        html.replace("__API_BASE__", root_path)
    )
