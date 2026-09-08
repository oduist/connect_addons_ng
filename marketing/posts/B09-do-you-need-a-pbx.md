---
id: B9
title: Do you need a PBX at all?
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/index.md, connect_twilio/docs/installation.md, connect_freeswitch/docs/admin/freeswitch-setup.md, connect/docs/user/callflows.md]
---

## Post

Most companies buy a PBX out of habit. A cloud number plus Odoo covers more than people expect. 📵

**What a cloud number already gives you** through `connect_twilio`: a browser softphone in the Odoo navbar, click-to-call from any phone field, inbound routing to a user or a call flow, multi-level IVR with DTMF or speech, ring groups, voicemail, call recording with in-browser playback, SIP credentials for desk phones, and SMS/WhatsApp. Nothing to install, nothing to patch.

**What still argues for a PBX** — `connect_freeswitch`: FIFO queues with music on hold and position announcements, call parking, a paired SIP firewall service, local Piper TTS for prompts, and a media path that never leaves your infrastructure. Costs: a host, ports 48082/tcp and 16000–17000/udp, and someone who owns the upgrade.

Either way it is the same Odoo call ledger and the same AI transcripts, so starting on a cloud number is not a dead end.

Would you still buy a PBX in 2026? 👇

#Odoo #VoIP #PBX #FreeSWITCH #Twilio

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Hosting",
  "headline": "A number is often",
  "headline_grad": "enough to start.",
  "lede": "Web phone, IVR, ring groups, recording and SMS work on a cloud number alone. *Queues, parking and a firewall are why you'd still host.*",
  "nodes": [
    {"t": "Cloud number", "s": "web phone · IVR · recording · SMS", "c": "provider"},
    {"t": "FreeSWITCH", "s": "queues · parking · firewall · local TTS", "c": "cyan"}
  ],
  "link_label": "same call ledger",
  "footer": "Start on a cloud number, move to your own PBX later"
}
```

## Notes

"Media path never leaves your infrastructure" is true of the FreeSWITCH
deployment; on Twilio the equivalent answer is `connect_s3` (recordings written
into your own AWS bucket), not the media path. Keep those two claims separate.
