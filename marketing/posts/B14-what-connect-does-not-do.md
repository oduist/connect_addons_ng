---
id: B14
title: What Connect deliberately does not do
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md, connect_infobip/docs/admin/infobip-setup.md, connect_bird/docs/admin/bird-setup.md, connect_vonage/docs/admin/vonage-setup.md, connect_3cx/docs/admin/3cx-setup.md, connect_livekit/docs/admin/livekit-setup.md]
---

## Post

Every integration page in our docs ends with a limitations section. Here they are, in one post, before you find them in a demo. 🚧

**Telnyx** — no WhatsApp voice calling; RCS is text plus SMS fallback, no rich cards; no attended transfer from the web phone; call-cost data can lag.
**Infobip** — no IVR or call flows in v1; no recorded voicemail; no RCS; no transfer from the web phone; the browser only receives calls while a tab is open.
**Bird** — no web phone at all (no WebRTC SDK), and until Bird ships messaging webhook events, inbound messages cannot be received and statuses are polled.
**Vonage** — ring groups ring sequentially; no simultaneous ring, call transfer, or WhatsApp/MMS sending.
**3CX** — calls appear only after they end; internal 3CX calls are not reported; recording audio stays on the PBX; no SMS, no web phone.
**LiveKit** — no SIP registrar, so hardphones cannot register; the carrier trunk is yours to bring.

We would rather you rule us out in five minutes than in month two.

Which gap would be a dealbreaker for you? 👇

#Odoo #VoIP #Telephony #Transparency #CPaaS

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Limitations",
  "headline": "What we don't do.",
  "headline_grad": "Per provider.",
  "lede": "Every provider page in the docs ends with its own limitations section. *Read them before the demo, not after.*",
  "tiles": [
    {"sym": "Tx", "nm": "Telnyx", "c": "provider"},
    {"sym": "Ib", "nm": "Infobip", "c": "provider"},
    {"sym": "Bd", "nm": "Bird", "c": "provider"},
    {"sym": "Vo", "nm": "Vonage", "c": "provider"},
    {"sym": "3CX", "nm": "3CX", "c": "provider"},
    {"sym": "LK", "nm": "LiveKit", "c": "provider"}
  ],
  "footer": "Limitations are documented per module, not buried"
}
```

## Notes

These lists move as versions ship — re-read every `Known limitations` /
`What this integration does not do` section immediately before publishing. The
Bird gap in particular is a Bird-platform issue that may disappear without any
change on our side. 3CX live call states exist on the optional AI-edition
sidecar agent, which is still mock-validated; the post intentionally describes
the base tier.
