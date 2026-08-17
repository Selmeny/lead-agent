---
title: "SPIKE-B — AU virtual number + inbound call / call-forward"
type: spike
project: P-lead-agent
status: findings-recorded
created: 2026-08-11
---

# SPIKE-B — One AU number to receive calls AND forward to owner

Goal: an AU number that (1) receives a real inbound call, (2) can forward /
route it to the owner's mobile, and ideally (3) also handles the SMS text-back.

## Key finding (changes the DECIDE)
**ClickSend AU numbers are SMS/MMS only. They CANNOT receive or forward voice
calls.** Call forwarding exists only for US/UK numbers, not AU. So ClickSend
alone cannot handle the call-forward leg.

## Verified options that CAN receive + forward AU calls
| Provider | Local AU number | Mobile AU num | Call-forward | Inbound call cost | Notes |
|----------|----------------|---------------|--------------|-------------------|-------|
| **Twilio** | $3.00/mo | (extra) | Yes (Studio/TwiML) | $0.0100/min | Voice + SMS on ONE number; AU1 region; mature API. USD. |
| Zadarma | ~$3/mo | $6/mo | Yes | Low/free per plan | Incoming calls free on plan. |
| FlyNumber | $2.95/mo | $14.95/mo | Yes | Low per-min | Caller ID preserved. |
| Sonetel | $2.39–2.69/mo | — | Yes | Local rates | App or direct forward. |
| Telnyx | $1–2/mo | — | Yes | Usage-based | SIP/app forward. |
| Call61 | $9.99/mo | — | Yes | Unlimited incoming | Simple sub; residential focus. |

## Two viable architectures
**Option A — Twilio does everything (recommended).**
- One Twilio AU local number (~$3/mo) supports BOTH voice recovery + SMS.
- Inbound call -> auto text-back (SMS) -> qualify -> forward call to owner.
- Single provider, single number, single billing. Matches engineering-director
  "reduce" principle: fewer moving parts.
- Cost: $3/mo number + SMS (~8c out, ~1.2c in) + $0.01/min inbound calls.

**Option B — ClickSend for SMS + cheap third-party (Zadarma/Sonetel/Telnyx) for call forward.**
- ClickSend SMS (~4.8–7.2c) + separate ~$2–3/mo forwarding number.
- Two providers, two numbers, two dashboards. More complexity.
- Only wins if you want to avoid Twilio entirely.

## Cost comparison (per client / month)
| | Option A (Twilio all-in) | Option B (ClickSend + 3rd party) |
|---|---|---|
| Number(s) | ~$3.00 | ~$2–3 + ClickSend ~$19 if dedicated |
| SMS out/in | ~8c/~1.2c | ~7.2c/free |
| Call-forward | included (Twilio) | separate provider |
| Complexity | LOW (one stack) | HIGH (two stacks) |
| Satisfaction of client phone-only handoff | YES | YES |

## Recommendation (pending DECIDE)
**Option A — Twilio all-in-one.** One AU number detects inbound calls (the missed-call
trigger) AND sends SMS. Handoff is a qualified-lead SMS summary to the owner —
**no call-forwarding** (see ANCHOR: forwarding every call defeats the value prop).
Keep voice detection on the Twilio number for the trigger; we do NOT route calls
to the owner.

## Open question for SPIKE-C / build
- Confirm ACMA Sender ID + consent for Twilio AU SMS (business messaging).
- Twilio requires a real AU number + account setup for the demo go-live.
