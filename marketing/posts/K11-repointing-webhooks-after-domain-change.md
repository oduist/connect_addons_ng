---
id: K11
title: Re-pointing webhooks after a domain change
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_vonage/docs/admin/vonage-setup.md, connect_elevenlabs/docs/configuration.md, connect_twilio/docs/configuration.md]
---

## Post

You moved Odoo to a new domain over the weekend. Everything works. Then the phone rings and nothing happens. 📵

Telephony is the one integration that notices a domain change immediately, because the provider calls *you*. In Oduist Connect all of those callback URLs are built from a single field — the core **API URL**.

So the fix is one field and one button per provider:

🔧 Set **API URL** to the new public HTTPS URL (Connect ▸ Configuration ▸ Settings)
📞 **Vonage** — re-run **SYNC VONAGE ACCOUNT**: the application's voice, messages and RTC webhook URLs are rewritten
🤖 **ElevenLabs** — **SYNC** re-pushes the conversation-initiation and post-call webhooks *and* every server tool URL; the post-call secret is rotated if the API URL drifted
☎️ **Twilio** — every webhook URL pushed to Twilio is built from the same value, and signature validation is computed against the exact URL, so a stale one fails closed

One source of truth beats hunting through three vendor consoles.

What broke first for you after a domain migration? 👇

#Odoo #Webhooks #Twilio #Vonage #Integration

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Webhooks",
  "headline": "One field rebuilds",
  "headline_grad": "every callback URL.",
  "lede": "Domain change? Fix the core *API URL*, then re-sync each provider — the callbacks are generated, never hand-typed.",
  "tiles": [
    {"sym": "API", "nm": "core setting", "c": "cyan", "hero": true},
    {"sym": "VN", "nm": "app webhooks", "c": "provider"},
    {"sym": "11L", "nm": "init + post-call", "c": "purple"},
    {"sym": "TOOL", "nm": "server tools", "c": "purple"},
    {"sym": "TW", "nm": "voice + msg", "c": "provider"},
    {"sym": "SIG", "nm": "URL-signed", "c": "core"}
  ],
  "footer": "Signature checks hash the exact URL — a stale callback fails closed, not silently"
}
```

## Notes

`connect_vonage` is not listed in AGENTS.md's module table; the module and its
admin guide do exist in the repo. Flag before publishing in case Vonage is not
yet an announced integration.
