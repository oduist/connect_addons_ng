---
id: C11
title: Try the whole stack with the all-in-one Docker file
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md, connect_freeswitch/deploy/docker-compose.full.yml]
---

## Post

Evaluating a phone system usually means a sales call before you've seen a single screen. Here's the alternative: one compose file that brings up the entire thing. 🧪

`docker-compose.full.yml` in **Oduist Connect** starts:

📦 Odoo 19 and PostgreSQL 16, with the addons repo mounted straight into the Odoo container — the Connect modules are there on first boot
☎️ FreeSWITCH, the SIP brute-force firewall, and Traefik as the TLS edge
🔊 Piper text-to-speech inside the FreeSWITCH image, so IVR prompts work with no cloud TTS account
🧭 Dial **9196** from the browser softphone for the echo test — signaling, media and codecs proven in one call, before you order a single trunk
🧹 Done looking? `docker compose down -v` and it's gone

One honest prerequisite: WebRTC and the TLS edge need a real certificate, so set a public FQDN in `FS_DOMAIN` and use the Let's Encrypt staging CA while you're still poking at it.

Nothing to request, nothing to schedule. Just read the compose file first — you'll learn more from it than from any demo.

What do you always check first when trying a new stack? 👇

#Odoo #Docker #FreeSWITCH #SelfHosted #VoIP

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Try it",
  "headline": "The whole stack,",
  "headline_grad": "one compose file.",
  "lede": "Odoo, Postgres, FreeSWITCH, the SIP firewall and the TLS edge — *up together*, addons already mounted, nothing to request.",
  "tiles": [
    {"sym": "19", "nm": "Odoo", "c": "app", "hero": true},
    {"sym": "PG", "nm": "Postgres 16", "c": "core"},
    {"sym": "FS", "nm": "FreeSWITCH", "c": "provider"},
    {"sym": "FW", "nm": "SIP firewall", "c": "memory"},
    {"sym": "TLS", "nm": "Traefik edge", "c": "cyan"},
    {"sym": "WEB", "nm": "Verto phone", "c": "magenta"}
  ],
  "footer": "docker compose -f docker-compose.full.yml up -d"
}
```

## Notes

The brief called this "on your laptop" — the compose file is not laptop-only:
it requires `FS_DOMAIN`, `ACME_EMAIL` and a publicly resolvable FQDN for the
Let's Encrypt certificate, and FreeSWITCH/Traefik run in host network mode.
The post is written for "one host" rather than "your laptop" for that reason.
Flag this if the docs article keeps the laptop framing.
