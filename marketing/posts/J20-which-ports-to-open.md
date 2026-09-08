---
id: J20
title: Which FreeSWITCH ports to open — and never expose
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

Half of self-hosted telephony support is firewall rules. Here's the whole list for a FreeSWITCH host running Oduist Connect. 🧱

**Open these:**
`48082/tcp` — Verto WSS, browser phone signaling
`16000-17000/udp` — RTP media (≈500 concurrent calls)
`5080/udp` + `5080/tcp` — SIP signaling on the sofia `external` profile
`443/tcp` — XML-RPC over HTTPS, Odoo → Traefik → FreeSWITCH

**Never expose these:**
`8080/tcp` — `mod_xml_rpc` plain HTTP. Traefik proxies to it; the image binds it to `127.0.0.1`
`8081/tcp` — firewall service plain HTTP, loopback-only, reached through `/firewall` on Traefik

The pattern: everything sensitive goes through the single TLS edge. `mod_xml_rpc` has no native TLS and its credential grants full control of the switch — originate, eavesdrop, eval.

Which port do you see wrongly opened most often on customer boxes? 👇

#Odoo #FreeSWITCH #Security

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Four ports open.",
  "headline_grad": "Two never public.",
  "lede": "Media and signaling face the world; the control plane stays on loopback behind *one TLS edge*.",
  "tiles": [
    {"sym": "48082", "nm": "Verto WSS", "c": "app"},
    {"sym": "16000+", "nm": "RTP media udp", "c": "app"},
    {"sym": "5080", "nm": "SIP udp + tcp", "c": "app"},
    {"sym": "443", "nm": "XML-RPC via TLS", "c": "cyan"},
    {"sym": "8080", "nm": "Never expose", "c": "core", "hero": true},
    {"sym": "8081", "nm": "Never expose", "c": "core", "hero": true}
  ],
  "footer": "Traefik is the single TLS edge — 8080 and 8081 stay bound to 127.0.0.1"
}
```

## Notes

Port list is the *Firewall Configuration* table. The 16000-17000 range is stated
as sufficient for roughly 500 concurrent calls and is configurable in
`switch.conf.xml`.
