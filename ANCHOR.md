---
title: "P-lead-agent — ANCHOR (next increment)"
type: graph-anchor
project: P-lead-agent
status: active
created: 2026-08-11
---

# ANCHOR — Speed-to-Lead: from demo to first paying client

## Real-world need (plain language)
A local trade business owner (plumber, electrician, pest control) misses calls
while on the job. Every missed call is a lost job. We sell them an automation
that texts the customer back in ~2 seconds, qualifies the lead, and hands it to
the owner by SMS + call-forwarding. The owner is phone-only: no website, no app.

## What is DONE (verified, not assumed)
- Demo live: https://paulbrugman.com/lead-agent/ — health returns `{"status":"ok"}`
- Agent brain (LLM + rule backends), qualification flow, handoff — working
- Docker + Traefik path route `/lead-agent` behind Cloudflare Tunnel
- FastAPI app, deterministic tests, deployed container Up 23h
- Git repo + pushed to GitHub (origin with token)

## Core design principle (do not break)
The tradie keeps working. The agent catches the call, qualifies the lead, and
hands off ONLY a qualified-lead summary by SMS. **No call-forwarding to the
owner** — forwarding every call defeats the product's value prop, which is
"we catch the calls you miss while you work." Owner calls the qualified lead
back when free.

## DONE criteria for THIS increment (testable facts)
1. One AU virtual number is live and can detect a missed incoming call.
2. A real inbound event (call or SMS) triggers the textback in <= ~2s.
3. Textback is sent as real SMS to a real mobile (AU provider: Twilio).
4. End-to-end test triggers: inbound event -> textback -> qualify -> qualified-lead SMS handoff to owner.
5. One business vertical is chosen (plumbers vs electricians vs pest).
6. One named client prospect is identified and the pitch is built.
7. Cost per client per month is known and margin is >= 70%.

## What we will NOT build now (guardrails)
- No WhatsApp channel (AU market is SMS + voice).
- No call-forwarding / voice routing to the owner's phone.
- No multi-tenant SaaS dashboard; one number per client, sim/demo scale.
- No full billing integration — a retainer agreement + manual invoicing is enough.
- No hard trust of a payment provider beyond Twilio trial credits.

## Stakeholders
- Director (you): sets metrics, guardrails, approves spend.
- Clients: phone-only trades, one AU number per client.
- Assistant (Hermes): runs the graph nodes, verifies with real output.

## Guardrails / failure policy
- Real SMS spend is gated: use trial credits first; no recurring cost without your OK.
- ACMA Sender-ID registration applies to business SMS — confirm compliance before go-live.
- No secrets in Telegram or chat. Credentials live in the server `.env` only.
- If an API/provider step fails, stop and report; do not invent a fake send.
