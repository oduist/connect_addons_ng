---
id: K03
title: Capacity planning — 1000 RTP ports
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md, connect_freeswitch/deploy/freeswitch/conf/autoload_configs/switch.conf.xml]
---

## Post

Nobody asks "how many concurrent calls can this box take?" until the day it stops taking them. 📈

The honest answer for a self-hosted Oduist Connect FreeSWITCH host is written in two config values, and you can read them in ten seconds:

🔢 **RTP range 16000–17000** — 1000 UDP ports, which is roughly **500 concurrent calls**
🚪 **max-sessions 1000** — the switch-level ceiling on live sessions
⏱️ **sessions-per-second 30** — the burst limit, the number that actually bites during a campaign, not the total
👥 Under 100 users? The defaults are more than adequate — don't tune what isn't the bottleneck
🔇 And the same range explains most "no audio" tickets: signaling works, UDP 16000–17000 is blocked

Both live in `switch.conf.xml`. Raising the ports is easy; remembering to open them on the cloud security group is what people miss.

What's your real observed peak — calls, not licences? 👇

#Odoo #FreeSWITCH #SIP #RTP #CapacityPlanning

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Your call ceiling",
  "headline_grad": "is two config values.",
  "lede": "Shipped defaults on a self-hosted FreeSWITCH host — *and what each one actually limits.*",
  "columns": ["Default", "Limits"],
  "rows": [
    {"f": "RTP port range 16000–17000", "m": ["1000", "~500 calls"]},
    {"f": "max-sessions", "m": ["1000", "sessions"]},
    {"f": "sessions-per-second", "m": ["30", "call bursts"]},
    {"f": "SIP signaling (sofia external)", "m": ["5080", "trunks"]},
    {"f": "Verto WSS (browser phone)", "m": ["48082", "web phone"]},
    {"f": "Deployments under 100 users", "m": ["defaults", "no tuning"]}
  ],
  "footer": "Set in switch.conf.xml — and mirrored in your cloud security group"
}
```

## Notes

The ~500-call figure is the documented rule of thumb (two RTP ports per call),
not a benchmarked result. Do not quote it as a tested throughput number.
