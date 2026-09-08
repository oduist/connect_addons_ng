---
id: N07
title: A sidecar that is never in the media path
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_asterisk/docs/admin/asterisk-setup.md, specs/decisions/026-asterisk-sidecar-agent.md]
---

## Post

The quickest way to make a customer's PBX your problem is to put your software between the phone and the audio. We designed the Asterisk integration to make that structurally impossible. 🎧

The sidecar agent next to your Asterisk does exactly four things: hold the AMI connection, forward call events to Odoo, upload recordings after hangup, and execute click-to-call originates. That's the list.

🔇 **It carries no media and no SIP signaling.** The JsSIP web phone registers over WSS straight to your Asterisk
📤 Agent → Odoo is **outbound-only HTTPS**, so it works behind NAT with no inbound firewall rule
🔌 Odoo → agent is needed only for actions. When that direction is unreachable, events and recordings keep flowing — you lose click-to-call, not call history
🔑 One shared token, `Authorization: Bearer`, in both directions
🛡️ The AMI account is scoped: `read = call,dialplan,user`, `write = originate,call,reporting`. The `system` and `command` classes are deliberately not granted

If our container dies at 3 a.m., your phones keep ringing. That is the requirement everything else was designed around.

Tell me why this is wrong. 👇

#Asterisk #Odoo #SoftwareArchitecture #VoIP #Integration

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Asterisk",
  "headline": "If the sidecar dies,",
  "headline_grad": "your phones don't.",
  "lede": "The agent holds AMI and nothing else. *Media and SIP go browser-to-Asterisk directly* — no third party in the audio path.",
  "nodes": [
    {"t": "Your Asterisk", "s": "FreePBX · Issabel · plain 13–21", "c": "provider"},
    {"t": "Sidecar agent", "s": "AMI events · originate · recordings", "c": "cyan"},
    {"t": "Odoo", "s": "call ledger · click-to-call · chatter", "c": "app"}
  ],
  "link_label": "Bearer",
  "footer": "Outbound-only HTTPS to Odoo · scoped AMI account, no system/command classes"
}
```

## Notes

Click-to-call *does* require Odoo → agent reachability (LAN, VPN or port
forward). The post says so; don't drop that caveat when shortening for X.
