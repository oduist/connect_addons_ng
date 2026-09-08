---
id: I04
title: Toll fraud protection
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/firewall.md]
---

## Post

Toll fraud doesn't announce itself. You find out when the carrier invoice arrives — a weekend's worth of minutes to destinations your business has never called. 💸

The difference between an incident and a bill is how fast an unauthorised call attempt is stopped.

In **Oduist Connect**, the FreeSWITCH firewall service treats it as its own event class:

🚫 An INVITE with no established session raises `sofia::wrong_call_state` — the IP is banned, not just logged
⏱️ The ban is written straight into `ipset`, so the next packet is dropped in the kernel instead of reaching the dialplan
✅ Trunk providers and office NAT exits go on the whitelist and are never touched
🧱 Whole VPS ranges can go on the blacklist as CIDR
📊 Every ban is an audit row in Odoo, with a one-click unban when it was your own phone

Nobody budgets for a fraudulent call. Which is why the block has to be automatic.

How is your PBX protected against call attempts from unknown sources today? 👇

#VoIP #TollFraud #FreeSWITCH #Odoo #Security

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Fraudulent minutes",
  "headline_grad": "you never pay for.",
  "lede": "The firewall service turns a suspicious call attempt into a *kernel-level drop* — and an audit row in Odoo.",
  "columns": ["Without the service", "With it"],
  "rows": [
    {"f": "Failed authentication logged", "m": ["✓", "✓"]},
    {"f": "Failed authentication auto-banned", "m": ["—", "✓"]},
    {"f": "Call attempt with no session banned", "m": ["—", "✓"]},
    {"f": "Scanner User-Agents dropped pre-PBX", "m": ["—", "✓"]},
    {"f": "Whitelist / CIDR blacklist in Odoo", "m": ["—", "✓"]},
    {"f": "Audit trail & one-click unban", "m": ["—", "✓"]}
  ],
  "footer": "sofia::wrong_call_state → ipset ban · survives container restarts"
}
```

## Notes

No fraud loss figures are claimed — we have none documented. Keep the money
angle qualitative.
