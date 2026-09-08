---
id: J08
title: Echo test 9196 proves the media path
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

Before you open a ticket with your carrier, dial **9196**. ☎️

It's the echo test on the FreeSWITCH stack behind Oduist Connect. Call it from any registered Verto or SIP phone and it plays back everything you say. Thirty seconds, and you've proven three things at once: signaling (WebSocket/SIP) is up, media (RTP/DTLS) flows **in both directions**, and codecs negotiated.

Hear nothing? That's not ambiguous either — check that **UDP 16000-17000** is open in your firewall. And in the FreeSWITCH log, look for "DTLS state from OFF to HANDSHAKE": if it never reaches ESTABLISHED, media ports are blocked.

Need one-way only? **9664** plays hold music — server to client, nothing coming back.

Half of all "no audio" tickets end at this test. What's your first-line check? 👇

#Odoo #FreeSWITCH #VoIP

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Two extensions,",
  "headline_grad": "no carrier ticket.",
  "lede": "*9196* echoes your own audio back — signaling, media both ways and codec negotiation proven in one call.",
  "tiles": [
    {"sym": "9196", "nm": "Echo test", "c": "cyan", "hero": true},
    {"sym": "9664", "nm": "Hold music", "c": "provider"},
    {"sym": "RTP", "nm": "16000-17000/udp", "c": "app"},
    {"sym": "WSS", "nm": "port 48082", "c": "app"},
    {"sym": "DTLS", "nm": "must reach ESTABLISHED", "c": "magenta"},
    {"sym": "SIP", "nm": "port 5080", "c": "provider"}
  ],
  "footer": "Silence on 9196 = blocked UDP media ports, not a carrier problem"
}
```

## Notes

Extension numbers, port ranges and the DTLS log line all come from the *Testing*
and *No audio on calls* sections of the FreeSWITCH setup doc.
