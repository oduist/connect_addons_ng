---
id: K02
title: The 8-point smoke test before go-live
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/customer-onboarding.md, connect_freeswitch/docs/admin/freeswitch-setup.md, connect_freeswitch/docs/admin/firewall.md]
---

## Post

"It rang, we heard each other, we're live." That test passes on a system that will still fail on Monday morning. ☎️

Before we declare a FreeSWITCH customer live, eight checks have to pass — each one with a documented fallback:

1️⃣ **Check Status** in Odoo returns `UP — <version>`
2️⃣ Dial **9196** — echo test proves signaling *and* two-way RTP
3️⃣ Dial **9664** — hold music proves one-way media
4️⃣ Outbound to a mobile — and the mobile shows the *right* caller ID
5️⃣ Inbound to **every** DID, not just the first one
6️⃣ Click-to-call from a partner form in Odoo
7️⃣ All of the above appear in Call History, with recordings
8️⃣ `GET /firewall/healthz` returns `{"status":"ok","odoo":true,"esl":true}`

Half of these are not "does the phone work" — they're "does the phone work *and* does Odoo know about it".

Which check would you add to this list? 👇

#Odoo #FreeSWITCH #VoIP #SIP #Ops

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Go-live",
  "headline": "Eight checks",
  "headline_grad": "before you say live.",
  "lede": "The FreeSWITCH go-live gate. *Each check has a documented failure path* — no check passes by opinion.",
  "tiles": [
    {"sym": "01", "nm": "Server status", "c": "provider"},
    {"sym": "9196", "nm": "Echo / RTP", "c": "provider"},
    {"sym": "9664", "nm": "Hold music", "c": "provider"},
    {"sym": "04", "nm": "Outbound PSTN", "c": "cyan"},
    {"sym": "05", "nm": "Every DID", "c": "cyan"},
    {"sym": "06", "nm": "Click-to-call", "c": "app"},
    {"sym": "07", "nm": "Call history", "c": "app"},
    {"sym": "08", "nm": "Firewall health", "c": "core"},
    {"sym": "GO", "nm": "Handover", "c": "magenta", "hero": true}
  ],
  "footer": "Then the handover record — FQDN, deploy path, vault reference, image tags"
}
```

## Notes

Test 8's JSON body is the dependency-aware readiness endpoint, not `/healthz`
(see the liveness-vs-readiness post, N11).
