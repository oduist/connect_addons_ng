---
id: F17
title: Inbound SMS that becomes a CRM lead
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_crm_twilio/docs/index.md, connect_crm/docs/configuration.md]
---

## Post

A prospect texts your business number instead of calling. In most setups that message dies in a provider inbox. 📲

With **Oduist Connect CRM** and the Twilio integration installed, a tiny bridge module wires the two together — and inbound messages can be routed to CRM:

📥 A Twilio message configuration gains **CRM Lead** as a destination
🔎 The sender's number is looked up with the same lead-matching logic used for calls — an existing lead is reused, otherwise a new one is created
🧩 The bridge installs itself automatically once both modules are present; there is nothing to configure in it
🏗️ It ships no views, no menus and no settings — one routing option, that's all
🔌 `connect_crm` stays provider-agnostic; the Twilio-specific glue lives in its own module

That last point is the architecture: keep the CRM logic portable, isolate the provider quirk in twelve lines of bridge.

SMS to your main business number — where does it land today? 👇

#Odoo #CRM #SMS #Twilio #LeadGeneration

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Messaging",
  "headline": "An inbound text",
  "headline_grad": "becomes a lead.",
  "lede": "Twilio message routing gains a *CRM Lead* destination — matched or created from the sender's number.",
  "nodes": [
    {"t": "Inbound SMS", "s": "Twilio number", "c": "provider"},
    {"t": "Message config", "s": "destination: CRM Lead", "c": "cyan"},
    {"t": "Lead", "s": "matched or created", "c": "app"}
  ],
  "link_label": "routed",
  "footer": "Auto-installed bridge · no views, no menus, no settings"
}
```

## Notes

"Twelve lines" is a figure of speech for a single model extension — do not quote
it as a measured line count. Routing must be configured on the Twilio message
configuration; it is not on by default.
