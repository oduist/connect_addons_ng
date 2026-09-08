---
id: K13
title: Per-call cost tracking in the ledger
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/configuration.md, connect_twilio/docs/maintenance.md, connect_twilio/models/call.py]
---

## Post

Here's a detail that surprises people: when a call ends, its price doesn't exist yet. ⏳

Twilio finalises call pricing asynchronously, some time after hangup. So "show the cost on the call record" can't be done at call-completion time — which is why Oduist Connect does it as a deferred batch instead:

💰 Turn on **Fetch Call Prices** in the Twilio settings (off by default — it costs API calls)
🕐 A cron runs **every 5 minutes** and picks up ended calls that have no price yet
🧾 Each priced call carries `price`, `price_unit` and `price_currency` on the call record itself
📅 The sweep only looks back **30 days**, so a long-disabled setting doesn't trigger a giant backfill when you switch it on
📊 From there it's an ordinary Odoo field — group and filter your call list by user, partner or period to attribute spend

No separate billing engine. The cost sits on the same record as the recording, the transcript and the customer.

Do you charge telephony back to departments, or absorb it centrally? 👇

#Odoo #Twilio #Telecom #FinOps #CostControl

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Twilio",
  "headline": "The call ends.",
  "headline_grad": "The price arrives later.",
  "lede": "Carrier pricing is finalised asynchronously, so cost capture is a *deferred 5-minute batch* — not a webhook side effect.",
  "tiles": [
    {"sym": "5m", "nm": "cron sweep", "c": "cyan", "hero": true},
    {"sym": "30d", "nm": "look-back", "c": "cyan"},
    {"sym": "opt", "nm": "off by default", "c": "core"},
    {"sym": "€", "nm": "price", "c": "app"},
    {"sym": "cur", "nm": "price_unit", "c": "app"},
    {"sym": "call", "nm": "same record", "c": "provider"}
  ],
  "footer": "Cost, recording, transcript and customer on one record — group it like any Odoo field"
}
```

## Notes

Cost tracking is real; a packaged **chargeback report** is not shipped — spend
attribution is done with standard Odoo grouping/filtering on the call list. Do
not promise a dedicated report view. Price fields are Twilio-provided
(`connect_twilio`), not core.
