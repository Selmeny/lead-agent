---
title: "DECIDE — Final stack lock"
type: decide
project: P-lead-agent
status: decided
created: 2026-08-11
---

# DECIDE — Locked final stack (from 3 spikes)

## Final stack
| Component | Decision | Why |
|-----------|----------|-----|
| **Provider / number** | **Twilio** — one AU virtual number | Detects the missed call (the trigger) AND sends SMS on ONE number. |
| **SMS send** | Twilio SMS API | ~8c out / ~1.2c in AUD; trial credits first. |
| **Missed-call trigger** | Twilio detects inbound call event (no forwarding) | Fires the ~2s text-back. |
| **Handoff** | Qualified-lead SMS summary to owner | NO call-forwarding (core value prop). Owner calls back when free. |
| **Channel** | SMS + voice (AU) | Not WhatsApp. |
| **LLM** | DeepSeek V4 Flash free (OpenRouter) | Matches cost policy. |
| **Deploy** | Existing FastAPI + Docker + Traefik at `/lead-agent` | Already live. |
| **Compliance** | GREEN — send from phone number, no Sender ID register; "Reply STOP" + sender identification | Verified in SPIKE-C. |

## Vertical (DONE criterion #5)
Recommended starting vertical: **plumbers** (high service urgency, frequent missed calls,
emergency work off-site). Final owner pick is yours — "plumbers" is the working default
until you say otherwise.

## Cost estimate (per client / month, AUD)
- Twilio AU number: ~$3.00
- SMS out/in: usage-based, low volume (tens of msgs/client/mo) — a few dollars
- LLM: DeepSeek V4 Flash free
- **Approx total per client: ~$5–10/mo vs retainer A$300–800/mo → margin ≥ 95%**
  (well above the 70% guardrail in ANCHOR).

## What this unlocks
- Task 5 (BUILD-1): wire real SMS send via Twilio.
- Task 6 (BUILD-2): inbound trigger -> text-back -> qualify -> SMS handoff (no call-forward).
- Task 7 (CHECKER), 8 (SYNTHESIZE), 9 (VERIFY).

## Single client prospect (DONE criterion #6)
Target one named local plumber for the demo go-live. To be identified in
Task 4 follows / client pitch phase. (Flag for you to name or let me research local plumbers.)
