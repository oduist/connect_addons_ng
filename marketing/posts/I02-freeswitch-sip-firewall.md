---
id: I02
title: Kernel-level SIP brute-force blocking
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/firewall.md, connect/docs/admin/security.md]
---

## Post

Put a SIP port on the public internet and it gets found. Not by a person — by scanners that sweep address space all day. 🛡️

`connect_freeswitch` ships a firewall service for exactly that, and it works below the PBX:

⚡ It listens to FreeSWITCH REGISTER / INVITE events on the ESL bus and moves source IPs between six `ipset` tables that an `iptables` chain in front of the SIP ports consults at line rate
⏳ A successful registration buys 7 days of trust (sliding); a failed authentication lands the IP in `connect_fw_banned` for 24 h
🧹 Known scanner User-Agents are dropped by a string match before they reach FreeSWITCH at all
📋 Every decision is an audit row in Odoo — with a whitelist, a CIDR blacklist and a one-click unban
🌐 IPv4 and IPv6 in parallel sets

The data plane lives in the host kernel, so it survives a container restart. Disabled by default; one toggle turns it on.

Is your SIP edge protected in the kernel, or in the dialplan? 👇

#Odoo #FreeSWITCH #VoIP #Security #SIP

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Brute force stops",
  "headline_grad": "before the PBX.",
  "lede": "ESL events in, `ipset` decisions out — with the *whitelist, audit log and unban button* living in Odoo.",
  "nodes": [
    {"t": "FreeSWITCH", "s": "REGISTER / INVITE events", "c": "provider"},
    {"t": "Firewall service", "s": "ipset + iptables, NET_ADMIN", "c": "core"},
    {"t": "Odoo", "s": "whitelist · events · unban", "c": "app"}
  ],
  "link_label": "kernel-level",
  "footer": "6 ipset tables · IPv4 + IPv6 · 30-day audit retention"
}
```

## Notes

The service is off by default and needs `network_mode: host` + `NET_ADMIN`. Say
so in replies — it is the most common deployment mistake.
