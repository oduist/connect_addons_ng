---
id: J03
title: Telnyx 404 UNALLOCATED_NUMBER means billing
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

**`404 / UNALLOCATED_NUMBER`.** Everyone reads that as "you dialled a number that doesn't exist." Usually it isn't. 💳

When a Telnyx account balance is exhausted, Telnyx rejects **every** origination with exactly that code — before any TeXML routing runs. No webhook. No CDR. Nothing in your logs to correlate. A wrong number and a broke account look identical from inside Odoo.

So Oduist Connect disambiguates it for you. The Telnyx phone widget calls `telnyx_check_call_failure()`, which fetches `GET /v2/balance` server-side, and when the available credit is `<= 0` it raises a sticky red notification naming the real cause. Connect Administrators also see the balance; plain users get the message without amounts.

The fix is a top-up, not a debugging session.

Ever lost an afternoon to an error code that meant something else entirely? 👇

#Odoo #Telnyx #Telephony

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · Telnyx",
  "headline": "404 doesn't always",
  "headline_grad": "mean wrong number.",
  "lede": "A billing-blocked Telnyx account rejects *every* origination with the same code — and produces no webhook and no CDR.",
  "bubbles": [
    {"side": "left", "who": "Telnyx", "text": "404 / UNALLOCATED_NUMBER — call rejected before routing"},
    {"side": "right", "who": "Odoo web phone", "text": "Telnyx balance is exhausted. Top up the account to restore calling."}
  ],
  "badge": "✓ GET /v2/balance checked server-side, key never exposed",
  "footer": "Sticky notification instead of a silent return to the keypad"
}
```

## Notes

Wording follows the "Billing-blocked account" warning block in the Telnyx setup
doc. Keep the "admins see amounts, users don't" nuance if the post is shortened.
