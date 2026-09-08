---
id: J09
title: CHECK STATUS says UNREACHABLE or AUTH FAILED
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

A health check that only says "failed" is useless. So the **CHECK STATUS** button on the FreeSWITCH settings form tells you *which side* to fix. 🩺

Five answers, five different jobs:

🟢 `UP — <version>` — healthy, go home.
⚪ `NOT CONFIGURED` — no XML-RPC host in Odoo; nothing was even attempted.
🔴 `UNREACHABLE` — the verified TLS connection to port 443 failed. Host, DNS, Traefik, firewall, or an untrusted certificate.
🟠 `AUTH FAILED` — reachable, but `mod_xml_rpc` rejected the managed credential (HTTP 401). Restart FreeSWITCH so it fetches the current one from Odoo.
🟡 `INVALID RESPONSE` — it answered, but the payload wouldn't parse. FreeSWITCH logs and `mod_xml_rpc` config.

Note the split: UNREACHABLE is a network problem, AUTH FAILED never is.

Does your monitoring tell you *where* to look, or just that something broke? 👇

#Odoo #FreeSWITCH #DevOps

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Not \"it failed\".",
  "headline_grad": "\"Fix this side.\"",
  "lede": "CHECK STATUS probes FreeSWITCH over XML-RPC and writes the *specific* reason into Server Status.",
  "bubbles": [
    {"side": "left", "who": "Server Status", "text": "UNREACHABLE — verified TLS to port 443 failed"},
    {"side": "right", "who": "What to do", "text": "Host, DNS, Traefik, port 443, public certificate"},
    {"side": "left", "who": "Server Status", "text": "AUTH FAILED — mod_xml_rpc returned HTTP 401"},
    {"side": "right", "who": "What to do", "text": "Restart FreeSWITCH so it fetches the current generated credential"}
  ],
  "footer": "UP · NOT CONFIGURED · UNREACHABLE · AUTH FAILED · INVALID RESPONSE"
}
```

## Notes

The five statuses and their remedies are the *Checking server status* table in
the FreeSWITCH setup doc. Keep the wording identical — people search these strings.
