---
id: J12
title: HMAC mismatch on ElevenLabs webhooks
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/webhooks-security.md, connect_elevenlabs/docs/maintenance.md]
---

## Post

Your AI agent takes calls beautifully. Nothing lands in Odoo afterwards. The log says **401 — HMAC signature mismatch**. 🔏

The post-call webhook is the one ElevenLabs authenticates *by signature only* — there's no custom header for it. The controller checks `ElevenLabs-Signature` in the form `t=<unix_ts>,v0=<hex_hmac_sha256>`, where the signed message is `"<t>.<raw_body>"` and the key is the stored webhook secret.

So a 401 has exactly three causes:
🔑 the stored secret no longer matches ElevenLabs → run **SYNC**
⏱️ the signed timestamp is more than **30 minutes** old (anti-replay)
🧱 a proxy altered the body — the HMAC is over the *raw* bytes

Seeing *"no webhook secret configured; run ElevenLabs sync"* instead? Same button: SYNC recreates the webhook entity and stores its secret.

Anyone else been bitten by a proxy that "helpfully" re-encoded a body? 👇

#Odoo #ElevenLabs #Webhooks

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · ElevenLabs",
  "headline": "The call was great.",
  "headline_grad": "The webhook was 401.",
  "lede": "Post-call delivery is authenticated by HMAC over `\"<t>.<raw_body>\"` — *raw* bytes, with a 30-minute replay window.",
  "bubbles": [
    {"side": "left", "who": "Odoo log", "text": "401 Unauthorized — HMAC signature mismatch on /connect_elevenlabs/post_call"},
    {"side": "right", "who": "Fix", "text": "Run SYNC to recreate the webhook and store its secret · check the timestamp is under 30 min · stop the proxy rewriting the body"}
  ],
  "badge": "✓ Secret stored manager-only, rotated automatically if the API URL drifts",
  "footer": "Initiation webhook and server tools use a token instead — two mechanisms, on purpose"
}
```

## Notes

Header format, the 30-minute tolerance and the three 401 causes are all in
`webhooks-security.md`; the SYNC remedy is the maintenance troubleshooting table.
