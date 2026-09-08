---
id: C03
title: How to connect FreePBX / Issabel / Asterisk to Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_asterisk/docs/admin/asterisk-setup.md]
---

## Post

Your dialplan doesn't change. Not one line. 🧩

That's the part people don't expect when they hear "Odoo integration" for an existing FreePBX, Issabel or plain Asterisk. **Oduist Connect** ships no PBX image and rewrites nothing — it listens.

🐳 One small sidecar container runs next to your PBX and holds the AMI connection
🔐 It needs a single AMI account: read `call,dialplan,user`, write `originate,call,reporting`. The `system` and `command` classes are deliberately not granted, and Odoo renders the `manager.conf` snippet for you
📡 Live call events, click-to-call and recording upload — both directions authenticated by one shared token
🌍 Agent → Odoo is outbound-only HTTPS, so it works behind NAT; a lost link stops click-to-call, not the event flow
🖥️ Optional browser SIP phone talks straight to Asterisk over WSS — the agent stays out of the media path

Your PBX keeps doing its job. Odoo finally sees it.

Running Asterisk next to Odoo today? What's missing? 👇

#Asterisk #FreePBX #Odoo #Telephony #CTI

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Asterisk",
  "headline": "Keep your dialplan.",
  "headline_grad": "Add Odoo.",
  "lede": "A sidecar agent holds the AMI link and forwards call events — *no PBX image, no SIP migration, no dialplan rewrite*.",
  "nodes": [
    {"t": "Asterisk / FreePBX", "s": "your existing PBX", "c": "provider"},
    {"t": "Odoo", "s": "call ledger · contacts · CRM", "c": "app"}
  ],
  "link_label": "sidecar agent",
  "footer": "Live AMI events · click-to-call · recording upload · JsSIP web phone"
}
```

## Notes

Supported range is Asterisk 13–21. The Odoo → agent direction needs the agent
URL reachable from Odoo (LAN, VPN or port forward) — worth stating in replies
so nobody plans a pure-cloud Odoo without a tunnel.
