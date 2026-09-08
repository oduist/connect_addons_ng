---
id: I11
title: Proxy your recordings
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md, connect_s3/docs/setup.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

A recording URL that plays without a login is a recording anyone with the link can play. Forwarded emails don't check permissions. 🔗

**Oduist Connect** has one setting for that: **Proxy Recordings** (Connect ▸ Configuration ▸ Settings).

🛡️ On — recording audio is served through Odoo and requires authentication, so playback follows the same record rules as the call itself
🌐 Off — the browser gets direct URLs to the provider's storage, which is convenient and exactly what you don't want in production
🪣 With S3 storage, Odoo reads the media back from a bucket that blocks all public access — the object never needs to be public
🧾 On Telnyx, recording callbacks can carry short-lived signed download URLs; Odoo keeps them for playback but redacts them from debug payloads so temporary credentials aren't persisted

One toggle decides whether "who can hear this call" is answered by your ERP or by whoever holds the link.

Check yours this week — is it on? 👇

#Odoo #Telephony #Security #DataProtection

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Recordings",
  "headline": "Don't hand out",
  "headline_grad": "provider URLs.",
  "lede": "*Proxy Recordings* serves audio through Odoo, so playback obeys the same access rules as the call.",
  "columns": ["Direct provider URL", "Proxy Recordings"],
  "rows": [
    {"f": "Playback in the call form", "m": ["✓", "✓"]},
    {"f": "Requires an Odoo login", "m": ["—", "✓"]},
    {"f": "Storage URL hidden from the browser", "m": ["—", "✓"]},
    {"f": "Access follows Connect record rules", "m": ["—", "✓"]},
    {"f": "Works with a fully private S3 bucket", "m": ["—", "✓"]},
    {"f": "Audio stays in an authenticated session", "m": ["—", "✓"]}
  ],
  "footer": "Connect ▸ Configuration ▸ Settings · General tab"
}
```

## Notes

The setting is provider-agnostic core config; the S3 and Telnyx details are
supporting examples, not separate switches.
