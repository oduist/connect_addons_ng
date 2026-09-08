---
id: F07
title: Collections calls with the right invoice
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_account/docs/configuration.md, connect_account/docs/index.md]
---

## Post

Collections calls fail in the first ten seconds — while you're searching for the invoice and the customer is deciding you're not serious. 💸

**Oduist Connect Account** puts it on screen instead. When a call is recorded, the customer's most recent qualifying invoice is attached to it, and the rule is deliberately narrow:

🧾 Customer invoices only — vendor bills, credit notes and other move types are never matched
✅ Posted only — drafts are ignored
💰 Not fully paid — a settled invoice is not a reason to call
🕐 The most recent qualifying one wins, by invoice date
📌 The call shows up on the invoice under a **Calls** button, and the AI summary is posted to the invoice chatter

That narrowness is the feature. A collections call that opens with the wrong document is worse than one that opens with none.

How does your finance team pull up the right invoice mid-call today? 👇

#Odoo #Accounting #Collections #AccountsReceivable #Telephony

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · Accounting",
  "headline": "Open with",
  "headline_grad": "the right invoice.",
  "lede": "Only *posted, unpaid customer invoices* qualify — the newest one is attached to the call.",
  "bubbles": [
    {"side": "right", "who": "Your team", "text": "\"Hi Anna — I'm calling about invoice INV/2026/0148, €4,200, due last Friday.\""},
    {"side": "left", "who": "Customer", "text": "\"Yes, I have it here. We can release it on Thursday.\""}
  ],
  "badge": "✓ Invoice linked to the call · summary posted to its chatter",
  "footer": "Vendor bills and credit notes are never matched — by design"
}
```

## Notes

Invoice number and amount in the card are fictional. Partner matching must
succeed first: no contact on the call means no invoice link.
