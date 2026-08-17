---
title: "SPIKE-C — AU SMS compliance (ACMA Sender ID + consent)"
type: spike
project: P-lead-agent
status: findings-recorded
created: 2026-08-11
---

# SPIKE-C — Compliance for AU business SMS

Research date: 2026-08-11.

## 1. ACMA SMS Sender ID Register (effective 1 July 2026)
- Applies ONLY to **alphanumeric / branded sender IDs** (e.g. a company name).
- **Messages sent from a phone number are NOT affected.** No registration, no
  "Unverified" labelling. (Confirmed: ACMA, Optus, AWS docs.)
- Our design sends from the **AU virtual phone number** (Twilio), not a branded
  name. So **no Sender ID registration is required** for our v1.
- If we later add a branded name at the top of the SMS, we must register it via
  the provider (needs ABN + identity verification + valid use case).

## 2. Spam Act 2003 — consent
- Applies to *commercial* electronic messages (marketing/promotional).
- **Recipient-initiated / purely factual transactional messages** (confirmations,
  service replies) generally do NOT require prior consent or unsubscribe.
- Our missed-call text-back is **recipient-initiated** (the customer called first).
  So consent burden is low.
- Caution: if the message contains promotional content (booking, pitch), it leans
  commercial → safer to keep the body factual and service-oriented.

## 3. Rules that still apply (even for transactional)
- **Identify the sender** clearly (business name + contact details in the message).
- Provide an easy opt-out: **"Reply STOP"** and honour it within 5 working days.
- Accurate sender — never impersonate or mislead.

## 4. Practical compliance steps for our v1 go-live
1. Send from the AU **phone number** (not a branded sender ID) → no ACMA register required.
2. Keep the text-back **factual / service-oriented** (emergency advice + one qualifying question).
3. Include business name + contact in the SMS so the customer knows who is texting.
4. Honour **"Reply STOP"** — add a small handler so comply is trivial.
5. If qualification leans promotional, get express opt-in at handoff.
6. Record consent/get an ABN identity ready in case a branded sender ID is wanted later.

## Conclusion / compliance status
**GREEN for v1.** Using a Twilio AU phone number avoids the Sender ID register
(which only hits branded names). Recipient-initiated text-back keeps the consent
burden low. Add "Reply STOP" + sender identification and we are compliant.
No blocker for the DECIDE node or the build.
