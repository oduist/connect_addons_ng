---
id: C05
title: Deploy a FreeSWITCH PBX for Odoo with Docker Compose
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

Your own PBX, for the price of a `docker compose up -d`. 🐳

The **Oduist Connect** FreeSWITCH stack is three containers: FreeSWITCH, a SIP brute-force firewall, and Traefik as the single TLS edge.

🧠 There are no PBX config files to maintain. Users, extensions, call flows, gateways and routes live in Odoo; FreeSWITCH fetches the XML per call over XML cURL
🔊 Piper TTS runs **inside** the image — 26 bundled neural voices, no cloud TTS bill and no audio leaving your host
🌐 Verto WebRTC softphone in the browser, translated into German, French, Italian and Russian
🔑 One gotcha: Odoo generates a webhook token on install and answers FreeSWITCH with 401 until you copy it into `FS_WEBHOOK_TOKEN`. Fail-closed by design — check it first when nothing registers
☎️ Dial **9196** for the echo test before you touch a trunk: it proves signaling, media and codec negotiation in one call

Self-hosted, no per-seat licence, no vendor holding your call history.

Would you run your own PBX, or is that a problem you'd rather rent? 👇

#FreeSWITCH #Odoo #Docker #VoIP #SelfHosted

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Your own PBX.",
  "headline_grad": "One compose file.",
  "lede": "FreeSWITCH asks Odoo for every routing decision, so *all your PBX configuration is Odoo data* — not files on a server.",
  "nodes": [
    {"t": "FreeSWITCH", "s": "docker compose up -d", "c": "provider"},
    {"t": "Odoo", "s": "users · IVR · gateways · routes", "c": "app"}
  ],
  "link_label": "XML cURL",
  "footer": "Local Piper TTS · Verto browser phone · SIP firewall · Traefik TLS edge"
}
```

## Notes

Ports to have ready in replies: 48082/tcp (Verto WSS), 16000–17000/udp (RTP),
5080 udp+tcp (SIP), 443 (XML-RPC behind Traefik).
