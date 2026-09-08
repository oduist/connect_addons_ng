---
id: K07
title: Bring your own SIP trunk
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md, connect_livekit/docs/admin/livekit-setup.md]
---

## Post

The fastest way to lose a telephony deal: tell the customer they have to change carriers. 📞

Oduist Connect doesn't sell you minutes, so it doesn't have to. Bring the trunk you already have:

🔌 **FreeSWITCH** — a SIP Gateway record holds proxy, username, password, realm, from-domain, expiry and retry. Registration trunk or IP-auth trunk (fill **Inbound IPs** and the ACL is generated for you)
♻️ Saving a gateway restarts the sofia external profile automatically — no `fs_cli`, no container touch
📍 **LiveKit** — a BYO carrier trunk too: LiveKit is a media layer *on top of* your carrier, not a replacement. Outbound address for calls out, carrier signaling IPs for calls in
🆔 Caller IDs are per-user with a system default, so one trunk can front many identities
🔎 Verify with one line: `sofia status gateway <name>` → State must be **REGED**

Your carrier contract, your numbers, your negotiating position. Ours is the software.

Which trunk provider would you want us to document first? 👇

#Odoo #SIP #FreeSWITCH #LiveKit #Telecom

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Trunks",
  "headline": "Keep your carrier.",
  "headline_grad": "Change the software.",
  "lede": "Register-auth or IP-auth SIP trunks on FreeSWITCH, BYO carrier trunks on LiveKit. *We never resell your minutes.*",
  "nodes": [
    {"t": "Your SIP carrier", "s": "existing contract · existing DIDs", "c": "provider"},
    {"t": "Oduist Connect", "s": "gateway · routes · caller IDs in Odoo", "c": "app"}
  ],
  "link_label": "BYO trunk",
  "footer": "Gateway saved in Odoo → sofia profile reloads itself → sofia status gateway = REGED"
}
```

## Notes

LiveKit's SIP bridge has **no SIP registrar** — hardphones cannot register to it.
Mention that if someone asks about desk phones on the LiveKit path.
