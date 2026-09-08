---
id: J07
title: Phones behind NAT don't receive calls
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

Outgoing calls work perfectly. Incoming calls never ring the desk phone. Classic NAT. 📡

The diagnosis is one command:

`fs_cli -x "sofia status profile external reg"`

Look at the registration contact. It must show the phone's **public** IP. If you see `10.x`, `172.16–31.x` or `192.168.x`, FreeSWITCH is dutifully sending INVITEs into a private address that means nothing on your network.

The sofia profile shipped with Oduist Connect already handles this: `aggressive-nat-detection`, `NDLB-received-in-nat-reg-contact`, `nat-options-ping` and `apply-nat-acl` detect the NAT, rewrite the stored contact to the received public IP:port, and keep the pinhole open. No per-user configuration.

If a private contact still shows up, verify those parameters are present — and after a module upgrade run `sofia profile external restart reloadxml`.

Still fighting NAT in 2026? Tell me where. 👇

#Odoo #FreeSWITCH #NAT

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "It dials out fine.",
  "headline_grad": "It never rings.",
  "lede": "Check the registration contact. A private `192.168.x` address there means the INVITE is going nowhere.",
  "nodes": [
    {"t": "SIP phone behind NAT", "s": "registers from a private network", "c": "core"},
    {"t": "sofia external profile", "s": "contact rewritten to public IP:port", "c": "provider"}
  ],
  "link_label": "NAT detection",
  "footer": "fs_cli -x \"sofia status profile external reg\""
}
```

## Notes

Parameter names and the diagnostic command are taken verbatim from the *NAT
Handling* and *Incoming calls not reaching SIP phone* sections.
