---
id: G11
title: Call parking with BLF lamps
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/user/parking.md, connect_freeswitch/docs/admin/parking.md]
---

## Post

"Call for John on 701." Somebody shouts it across the office, and John — who is standing at the printer — picks it up from the nearest phone. 📞

That's call parking: a shared hold that anyone in the office can retrieve, unlike the private hold on your own handset.

**Oduist Connect** on FreeSWITCH wires it up out of the box:

🅿️ Six slots (701–706) created on install; add or rename as many as you like
💡 **BLF lamps** — program a DSS key per slot on a desk phone (`701@your-pbx`) and the lamp turns red when the slot is occupied. The whole office sees which slots are busy, in near real time
🖱️ Park from the Verto widget's Parking tab, from the **Park** button on the call record, or from a DSS key
📥 Retrieve the same three ways — the phone rings you back and bridges you to the parked party
♻️ Slots are Odoo records; the dialplan is rendered on the fly, so adding a slot never restarts FreeSWITCH

Parking is a hand-off, not a parking lot — park and announce, don't abandon.

Still using "hold and hope"? 👇

#Odoo #FreeSWITCH #VoIP #Telephony #SIP

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Parking",
  "headline": "Park it on 701.",
  "headline_grad": "The office sees it.",
  "lede": "Shared parking slots with *BLF lamps on desk phones* — park and retrieve from the widget, the call form or a DSS key.",
  "tiles": [
    {"sym": "701", "nm": "Busy · lamp red", "c": "core", "hero": true},
    {"sym": "702", "nm": "Free", "c": "app"},
    {"sym": "703", "nm": "Free", "c": "app"},
    {"sym": "704", "nm": "Free", "c": "app"},
    {"sym": "705", "nm": "Free", "c": "app"},
    {"sym": "706", "nm": "Free", "c": "app"}
  ],
  "footer": "mod_valet_parking · no FreeSWITCH restart to add a slot"
}
```

## Notes

Six default slots ship in `data/parking_slots.xml`; keep the total ≤ 8 so the
widget grid fits. Requires `connect_freeswitch` ≥ 19.0.1.7.0.
