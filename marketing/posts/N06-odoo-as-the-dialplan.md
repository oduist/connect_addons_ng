---
id: N06
title: Odoo as the dialplan via mod_xml_curl
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md, connect_freeswitch/docs/admin/parking.md]
---

## Post

The FreeSWITCH host in an Oduist Connect deployment has almost no configuration on it. The dialplan is an HTTP response. 🌐

FreeSWITCH's `mod_xml_curl` lets the switch ask an external service for XML at runtime. We pointed it at Odoo:

📇 **Directory binding** — a phone registers, Odoo answers with that user's credentials and dial-string
🗺️ **Dialplan binding** — a call arrives, Odoo renders the routing XML from your DIDs, extensions, call flows and outgoing routes
⚙️ **Configuration binding** — sofia gateways come back the same way
🅿️ Which is why adding a parking slot needs no restart: the dialplan for it is generated on the next dial
🔐 Every request carries a shared token and **fails closed** — registrations, lookups, CDRs and recording uploads all 401 until the container is paired

The cost, stated plainly: Odoo is now in the call-setup path. If Odoo is down, new calls don't route. We accept that because the alternative is configuration living in two places and drifting.

Would you have put a cache in front of it? Tell me why this is wrong. 👇

#Odoo #FreeSWITCH #VoIP #SoftwareArchitecture #SIP

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "The dialplan lives",
  "headline_grad": "in your database.",
  "lede": "`mod_xml_curl` asks Odoo for directory, dialplan and sofia XML at runtime. *Change a route, the next call uses it* — no reload.",
  "nodes": [
    {"t": "FreeSWITCH", "s": "asks for XML on every lookup", "c": "provider"},
    {"t": "Odoo", "s": "renders directory · dialplan · gateways", "c": "app"}
  ],
  "link_label": "mod_xml_curl",
  "footer": "Shared-token auth, fail-closed: unpaired container gets 401 on everything"
}
```

## Notes

The "Odoo is in the call-setup path" trade-off is deliberately stated. Real
mitigation in the product is deployment-level (Odoo availability), not a cache —
do not invent one in replies.
