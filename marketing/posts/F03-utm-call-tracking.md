---
id: F03
title: UTM attribution by phone number
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_crm/docs/configuration.md]
---

## Post

Your dashboard attributes every web form perfectly and every phone call to "unknown". For a lot of businesses, the phone is where the money actually is. 📈

Call tracking in **Oduist Connect CRM** closes that hole using standard Odoo UTM:

📱 Give a campaign its own inbound number and put that number on the UTM **Source**
🔒 The number is unique across sources — reusing one is refused with an error, so attribution can't quietly overlap
📞 On an incoming call, Connect looks up the source matching the *called* number and stamps it on the call
🎯 When a lead is created from that call — automatically or from the call form — the source is copied to the lead
📊 From there it's plain Odoo reporting: campaign, source and revenue in the funnel you already use

No tracking script, no third-party call-tracking subscription, no separate portal.

Which channel would you finally measure properly with a number of its own? 👇

#Odoo #CallTracking #MarketingAttribution #CRM #UTM

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Attribution",
  "headline": "A number per campaign.",
  "headline_grad": "Attribution for free.",
  "lede": "Put the campaign's number on a *UTM Source* — inbound calls to it are stamped with that source, and so is the lead they create.",
  "nodes": [
    {"t": "Campaign number", "s": "inbound DID", "c": "provider"},
    {"t": "UTM Source", "s": "unique phone field", "c": "cyan"},
    {"t": "Lead", "s": "source pre-filled", "c": "app"}
  ],
  "link_label": "on ring",
  "footer": "Standard Odoo UTM · no external call-tracking service"
}
```

## Notes

Attribution is triggered on the *called* number for incoming calls only. Buying
per-campaign DIDs is a provider-side cost — say so if pricing comes up.
