---
id: J10
title: Odoo rejects your self-signed certificate
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

"Odoo won't talk to my FreeSWITCH — it rejects my certificate. Can I just disable verification?" 🔐

No. And that's the feature.

Odoo reaches FreeSWITCH over XML-RPC, and **certificate verification is always enabled**, so a staging or self-signed certificate fails and CHECK STATUS reports UNREACHABLE. `mod_xml_rpc` has no native TLS at all — Traefik terminates HTTPS in front of it and proxies to the internal `127.0.0.1:8080` port.

Why so strict? That channel carries HTTP Basic Auth for a credential that grants **full control of the switch**: originate, eavesdrop, eval. Anyone able to observe the network path could lift it.

The fix is the boring one: set `FS_DOMAIN` and `ACME_EMAIL` in `deploy/.env` and let Traefik get a real Let's Encrypt certificate. If you pointed `ACME_CASERVER` at staging while testing the edge, switch back to the production CA first.

Where do you draw the "just disable it" line? 👇

#Odoo #FreeSWITCH #Security

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "It's not strict.",
  "headline_grad": "It's the control plane.",
  "lede": "XML-RPC carries a credential that can originate, eavesdrop and eval. Verification is *always* on — by design.",
  "columns": ["Odoo accepts"],
  "rows": [
    {"f": "Let's Encrypt production certificate", "m": ["✓"]},
    {"f": "Let's Encrypt staging (ACME_CASERVER)", "m": ["—"]},
    {"f": "Self-signed development fallback", "m": ["—"]},
    {"f": "Untrusted CA or mismatched hostname", "m": ["—"]},
    {"f": "Turning verification off", "m": ["—"]}
  ],
  "footer": "Set FS_DOMAIN + ACME_EMAIL in deploy/.env and let Traefik issue the cert"
}
```

## Notes

The self-signed fallback exists for local development (the entrypoint generates
it when no ACME cert is available) — it just isn't accepted by Odoo's XML-RPC
client. Worth clarifying if someone asks in the comments.
