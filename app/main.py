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

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .agent import make_agent, Lead

app = FastAPI(title="Lead-Agent Demo")
app.mount("/static", StaticFiles(directory="static"), name="static")

_agent = make_agent()
_LEADS: dict[str, Lead] = {}


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _ts() -> str:
    return time.strftime("%H:%M:%S")


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.post("/api/call")
async def simulate_call(req: Request):
    """Simulate a customer's missed call → create lead → return the textback."""
    body = await req.json()
    customer_phone = body.get("customer_phone", "+61400000000")
    first_message = body.get(
        "message",
        "hi, my water heater is leaking and water is going everywhere. are you open?",
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
async def customer_reply(req: Request):
    body = await req.json()
    lead_id = body.get("lead_id")
    message = body.get("message", "").strip()
    if not lead_id or lead_id not in _LEADS:
        return JSONResponse({"error": "unknown lead_id"}, status_code=404)
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)

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


@app.get("/api/leads")
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
