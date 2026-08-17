---
title: "SPIKE-A — AU SMS provider: ClickSend vs Twilio"
type: spike
project: P-lead-agent
status: findings-recorded
created: 2026-08-11
---

# SPIKE-A — Pick AU SMS provider (ClickSend vs Twilio)

Research date: 2026-08-11. Figures are AUD unless stated. Source = latest
published pricing (official pages + 2026 AU-focused reviews).

## ClickSend (AUD, pay-as-you-go, no subscription)
- **Boost tier:** 7.20c / SMS (under 5,000 msgs). Min top-up $20.
- **Growth:** 6.70c (5k+, $500 top-up).
- **Scale:** 6.20c (50k+, $3,000).
- **Enterprise:** 5.70c (150k+, $10,000).
- **50% bonus on first top-up** → effective first-rate as low as ~3.80–4.80c.
- **Inbound SMS: free.**
- **Dedicated AU number:** ~$19/mo.
- Free trial credits available. 12-month credit expiry on inactivity.

## Twilio (billed in USD)
- **Outbound SMS (mobile or alphanumeric sender):** $0.0515 / segment
  (~8.0c AUD at ~1.55 FX).
- **Inbound SMS:** $0.0075 (~1.2c AUD).
- **MMS:** $0.35 (~54c AUD) — not needed for us.
- **Phone number:** $8.25/mo (~$12.80 AUD).
- Volume tiers: ~7.3c AUD at 150k+.
- Billed in USD → FX variability risk.

## Comparison for OUR use case (one client, low volume)
| Factor | ClickSend | Twilio |
|--------|-----------|--------|
| Currency | AUD (stable) | USD (FX risk) |
| Outbound SMS (start) | 7.20c, ~4.8c with first top-up bonus | ~8.0c |
| Inbound SMS | FREE | ~1.2c |
| Dedicated AU number | ~$19/mo | ~$12.80/mo |
| AU-correct (local provider) | Yes | Global, USD-centric |
| Trial credits | Yes | Demo credits |
| Call-forward / voice | Available (address in SPIKE-B) | Yes, more mature voice API |
| Setup ease | Simple AU SMS API | Developer-grade |

## Preliminary recommendation (pending DECIDE node)
**ClickSend** for this use case:
- Cheaper outbound per SMS in real terms (esp. first top-up bonus).
- **Free inbound SMS** — our inbound trigger is SMS text-back, so this saves money.
- Billed in AUD — no FX surprises for cost-sensitive operation.
- AU-native provider, simpler for a phone-only-client SMB product.
- Dedicated number ~$19/mo is acceptable at one-number-per-client scale.

Twilio only if we later need advanced voice/call-forward API beyond ClickSend's
offering — revisit in SPIKE-B (number + call-forward) before final DECIDE.

## Open questions for SPIKE-B
- Does ClickSend provide an AU number that can RECEIVE a call and forward/call-forward?
- Trial credit limit for outbound SMS testing.
- Sender ID registration interacts with ACMA (see SPIKE-C).
