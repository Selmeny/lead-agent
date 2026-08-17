# Lead-Agent — Speed-to-Lead SMS Automation for Local Australian Trades

A working **demo** of a speed-to-lead agent for phone-only local businesses (plumbers,
electricians, etc.). Simulates the full flow: **missed call → auto SMS textback →
qualify the lead → hand off to the (phone-only) business owner.**

Built for the Australian market where **SMS + phone** dominate (not WhatsApp), and
where clients often have no website, no apps — just a phone number.

> ⚠️ **This is a DEMO.** Real SMS/voice delivery (ClickSend/Twilio) and the client's
> phone line are NOT wired — that's the client-dependent step requiring a real AU
> number + provider account. The agent brain, qualification flow, and handoff are
> fully functional.

## Live demo
- **https://paulbrugman.com/lead-agent/** — click "Simulate missed call", then reply as the customer (suburb → issue → urgency → name + mobile). Watch it qualify and hand off to the owner.

## How it works
```
CUSTOMER dials business -> missed
        |
        v
[AUTO TEXTBACK ~2s] emergency advice + first qualifying question
        |
        v  (customer replies by SMS)
[QUALIFY] suburb, issue, urgency, name + mobile  (one question at a time)
        |
        v
[HAND OFF] SMS summary + call-forward to the owner (phone-only client)
```
Owner interaction is **SMS + call-forwarding only** — no website, no app, no dashboard.

## Tech stack
- **FastAPI** + Uvicorn (small, self-hostable)
- **Agent brain:** pluggable backends
  - `LLMBackend` — DeepSeek V4 Flash via OpenRouter (real AI replies, AU-tuned prompt)
  - `RuleBackend` — deterministic offline fallback (also does field extraction for both)
- **Docker Compose + Traefik** — deployed under `/lead-agent/` behind Cloudflare Tunnel
- Leads + session state in-memory (demo scale)

## Project layout
```
app/
  agent.py      # business facts, Lead model, LLM + rule backends, field extraction
  main.py       # FastAPI: /api/call, /api/reply, /api/leads, /api/health, / UI
static/
  index.html    # WhatsApp-style demo chat UI
test_agent.py   # deterministic agent tests (no LLM needed)
Dockerfile
docker-compose.yml   # Traefik path route /lead-agent
```

## Run locally
```bash
# rule backend (no key needed)
uvicorn app.main:app --port 8000

# LLM backend
export OPENROUTER_API_KEY=sk-...
uvicorn app.main:app --port 8000
```

## Test
```bash
python test_agent.py
python test_agent_comprehensive.py
python test_rate_limit.py   # rate limiting on /api/call + /api/reply
```

## API
- `POST /api/call` → simulate missed call, returns textback + `lead_id`
- `POST /api/reply` `{lead_id, message}` → customer reply; returns agent reply + handoff when qualified
- `GET /api/leads` → all demo leads (requires `LEADS_ADMIN_TOKEN`)
- `GET /api/health`

## Rate limiting
`/api/call` and `/api/reply` are public POST endpoints that each trigger an LLM
call, so they're rate-limited per client IP via `slowapi` (in-app). The UI, static
files, `/api/health` and auth-gated `/api/leads` are **not** limited. Keyed on the
real client IP — it prefers `CF-Connecting-IP` / `X-Forwarded-For` (so it works
per-customer behind the Cloudflare Tunnel + Traefik path-prefix where all requests
share one upstream IP), falling back to the socket peer address. Tune per client
via env:

```bash
RATE_LIMIT_CALL=10/minute    # default; lookups / missed-call webhooks
RATE_LIMIT_REPLY=30/minute   # default; ongoing SMS conversation replies
```

Exceeding the limit returns **429 Too Many Requests**. See `test_rate_limit.py`.

## Deploy / version check
`/api/health` reports `version` = the git SHA baked into the image at build time
(`APP_VERSION` ARG). Confirm the live deploy matches a commit:

```bash
curl -s https://paulbrugman.com/lead-agent/api/health
# {"status":"ok","version":"<sha>","admin_token_configured":false}
```

## Business context (side-income idea)
Speed-to-lead automation sold as a retainer (**A$300–800/mo**) to no-website trades.
Operator owns the virtual AU number + agent stack per client; client forwards their
line and receives handoffs via SMS + call-forwarding. ~85% margin. Australia-correct:
**SMS + voice, not WhatsApp**; ACMA Sender-ID registration applies for business SMS.

## Status
Demo v1 complete and deployed. Next: wire real SMS/voice (ClickSend/Twilio + AU number)
for a paying client; pick a vertical (plumbers vs electricians); build client pitch.
