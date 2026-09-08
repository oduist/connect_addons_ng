---
id: I03
title: How a SIP scanner is dropped
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/firewall.md]
---

## Post

Every SIP handshake is a small trust decision, repeated thousands of times a day. Here is how **Oduist Connect** makes it — described from the defender's side. 🧱

1️⃣ A REGISTER arrives. FreeSWITCH answers with a 401 challenge, and the source IP lands in two sets at once: a 30-second window to answer, and a 24-hour default-deny if it never does.
2️⃣ Correct credentials → `sofia::register` → the IP moves to `authenticated` for 7 days, sliding. Traffic is accepted.
3️⃣ Wrong credentials → `sofia::register_attempt` with `auth-result=FORBIDDEN` → the IP moves to `banned` for 24 hours. Further packets are dropped in the kernel.

Default-deny, not default-allow: an address that starts a handshake and never finishes it ends up blocked, not forgotten.

Whitelisted trunks and office IPs short-circuit the whole pipeline, and every transition is an audit row in Odoo.

Which do you trust more for a public SIP edge — fail2ban parsing logs, or event-driven `ipset`? 👇

#FreeSWITCH #SIP #Security #Odoo #VoIP

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Six ipset tables.",
  "headline_grad": "One trustworthy port.",
  "lede": "Each SIP source sits in exactly one state — and the *kernel* enforces it at line rate.",
  "tiles": [
    {"sym": "WL", "nm": "whitelist · always accept", "c": "app"},
    {"sym": "AU", "nm": "authenticated · 7 d", "c": "app"},
    {"sym": "ES", "nm": "challenge window · 30 s", "c": "cyan"},
    {"sym": "EL", "nm": "default-deny · 24 h", "c": "magenta"},
    {"sym": "BN", "nm": "auto-ban · 24 h", "c": "core", "hero": true},
    {"sym": "BL", "nm": "blacklist · always drop", "c": "core"}
  ],
  "footer": "Event-driven from the FreeSWITCH ESL bus · full audit trail in Odoo"
}
```

## Notes

Defensive framing only — no scanning tools, payloads or reproduction steps. TTLs
quoted are the shipped defaults and are configurable in settings.
