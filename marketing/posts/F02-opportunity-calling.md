---
id: F02
title: See which opportunity is calling
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_crm/docs/configuration.md, connect_crm/docs/index.md]
---

## Post

The phone rings. You have about four seconds to remember who this is and what you promised them last time. 📞

**Oduist Connect CRM** matches the call to an open opportunity *while it is still ringing*, so the answer is on screen before you pick up:

🔎 Incoming calls are matched on the caller's number, outgoing on the number dialled
📇 The lookup runs against active leads in non-won stages, on both phone and mobile
🔢 It tries the stripped number, the `+` form and the E.164 form — formatting differences don't break it
🧯 Short numbers and unknown callers are skipped, so internal extensions never match a lead
🔗 Matching only *links* an existing lead — it never creates one; creation is a separate, explicit rule

The linked lead shows up in the active-calls widget and on the call form, and a **Calls** stat button on the lead gives you the whole history back.

Whose name do you wish you saw on an inbound ring? 👇

#Odoo #CRM #CTI #Sales #Telephony

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · CRM",
  "headline": "Know the deal",
  "headline_grad": "before you say hello.",
  "lede": "While the call is still ringing, Connect finds the caller's *open opportunity* and puts it on the screen.",
  "nodes": [
    {"t": "Inbound call", "s": "caller number", "c": "cyan"},
    {"t": "Open lead", "s": "non-won stage", "c": "app"}
  ],
  "link_label": "matched live",
  "footer": "Links existing leads only · creation is a separate, explicit rule"
}
```

## Notes

If several leads match, the most recent wins and a warning is logged — worth
mentioning in replies about duplicate leads.
