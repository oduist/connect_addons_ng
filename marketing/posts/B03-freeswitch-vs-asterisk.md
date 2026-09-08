---
id: B3
title: FreeSWITCH vs Asterisk with Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md, connect_asterisk/docs/admin/asterisk-setup.md, connect/docs/user/callflows.md]
---

## Post

"We already run Asterisk. Are you going to make us throw it out?" — no. That is exactly why there are two self-hosted paths. 🔧

**Keep your Asterisk** (`connect_asterisk`): FreePBX, Issabel or plain Asterisk 13–21. A thin sidecar agent holds the AMI connection, forwards call events to Odoo, uploads MixMonitor recordings and executes click-to-call. Your dialplan keeps working exactly as written — Odoo only listens. The JsSIP web phone talks SIP over WebSocket straight to your PBX; the agent is never in the media path.

**Start fresh with FreeSWITCH** (`connect_freeswitch`): a ready Docker image where FreeSWITCH asks Odoo for every routing decision over XML cURL. Users, extensions, call flows, gateways and outbound routes are configured in Odoo. You also get FIFO queues, call parking, local Piper TTS and a paired SIP firewall service.

One keeps your investment. The other moves the whole dialplan into Odoo.

Which would you pick for a 30-seat office? 👇

#Asterisk #FreeSWITCH #Odoo #VoIP #SelfHosted

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Self-hosted",
  "headline": "Keep the PBX,",
  "headline_grad": "or move it into Odoo.",
  "lede": "Asterisk stays as it is and Odoo listens over an AMI sidecar. FreeSWITCH asks Odoo for *every* routing decision.",
  "columns": ["Asterisk", "FreeSWITCH"],
  "rows": [
    {"f": "Keeps your existing dialplan", "m": ["✓", "—"]},
    {"f": "No new PBX to build", "m": ["✓", "—"]},
    {"f": "Browser web phone", "m": ["✓", "✓"]},
    {"f": "Routing & IVR configured in Odoo", "m": ["—", "✓"]},
    {"f": "Queues & call parking in Odoo", "m": ["—", "✓"]},
    {"f": "Local Piper TTS included", "m": ["—", "✓"]},
    {"f": "SIP firewall service", "m": ["—", "✓"]}
  ],
  "footer": "Both self-hosted · both feed the same Odoo call ledger"
}
```

## Notes

Asterisk-side caveats for the comments: click-to-call needs Odoo to reach the
agent URL (LAN, VPN or port forward), and recording upload requires the monitor
directory mounted into the agent container. Events and recordings keep flowing
even when Odoo cannot reach the agent.
