---
id: A07
title: Self-hosted vs cloud telephony for Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md, connect_twilio/docs/index.md, connect_twilio/docs/installation.md, connect_s3/docs/index.md, connect_livekit/docs/admin/livekit-setup.md]
---

## Post

What does self-hosting your Odoo telephony actually buy you? Not "cheaper minutes" — you still need a carrier either way. ⚖️

**Cloud (Twilio, Telnyx, Infobip, Vonage)** — nothing to run. A number, a browser phone, webhooks over HTTPS, and the provider's IVR/TTS. Recordings and media live on their side, unless you switch Twilio recordings into your own AWS S3 bucket.

**Self-hosted (FreeSWITCH, LiveKit)** — you run a Docker stack and you own the media path:
🧱 FreeSWITCH asks Odoo for every routing decision over XML cURL — users, extensions, call flows, gateways all configured in Odoo.
🗣️ Piper TTS runs locally, 26 bundled voice models, no cloud TTS in the loop.
🛡️ A paired SIP firewall service watches ESL and drives iptables on the host.
📞 LiveKit adds WebRTC video + a SIP bridge — but it sits *on top of* your carrier trunk, not instead of it.

The bill you trade is a server, ports and an upgrade path.

Which side are you on, and why? 👇

#Odoo #FreeSWITCH #SelfHosted #VoIP #Twilio

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Hosting",
  "headline": "Rent the stack,",
  "headline_grad": "or own the stack.",
  "lede": "Cloud CPaaS gives you nothing to run. FreeSWITCH gives you the media path, the prompts and the firewall. *Same Odoo either way.*",
  "columns": ["Cloud", "Self-hosted"],
  "rows": [
    {"f": "No server to operate", "m": ["✓", "—"]},
    {"f": "Browser web phone", "m": ["✓", "✓"]},
    {"f": "IVR & call flows in Odoo", "m": ["✓", "✓"]},
    {"f": "Media path under your control", "m": ["—", "✓"]},
    {"f": "Local TTS, no cloud voice", "m": ["—", "✓"]},
    {"f": "SIP firewall service included", "m": ["—", "✓"]},
    {"f": "Queues & call parking", "m": ["—", "✓"]}
  ],
  "footer": "FreeSWITCH & LiveKit ship as Docker stacks in the repo"
}
```

## Notes

"Queues & call parking" is FreeSWITCH-specific (FS Queues, parking). Twilio has
call flows and voicemail but no Odoo-managed queue — keep the row wording
about queues, not about IVR.
