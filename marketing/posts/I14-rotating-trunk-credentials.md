---
id: I14
title: Rotating trunk credentials without dropping calls
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

SIP trunk password rotation is the maintenance nobody schedules — because the last attempt meant editing a config file, restarting the PBX and explaining the silence to the sales floor. ☎️

In **Oduist Connect** it's a form save:

📝 Open Connect ▸ FreeSWITCH ▸ Gateways, paste the new password, Save. The save schedules a post-commit `sofia profile external restart reloadxml`
⚡ FreeSWITCH re-reads the gateway XML through xml_curl and re-registers within a few seconds — no container touched, no file edited
🔁 Order matters: set the new password at the provider **first**, then in Odoo. Between the two steps registration sits in `FAIL_WAIT`, so keep the window short
✅ Verify with `sofia status gateway <name>` — `State` must be `REGED` — then one outbound and one inbound test call
↩️ Wrong value? Write the previous password back on the same record; the profile restarts again

The password field is visible to Connect admins only, and the whole thing is a documented runbook, not tribal knowledge.

When did you last rotate a trunk credential? Honestly. 👇

#FreeSWITCH #VoIP #Odoo #SecOps #Runbook

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "Rotate the trunk.",
  "headline_grad": "Keep the calls.",
  "lede": "Saving a new gateway password triggers a profile reload — *re-registration in seconds*, no container restart.",
  "nodes": [
    {"t": "Odoo gateway record", "s": "password · Connect admins only", "c": "app"},
    {"t": "FreeSWITCH", "s": "xml_curl re-read · REGED", "c": "provider"}
  ],
  "link_label": "reload in seconds",
  "footer": "Documented runbook: coordinate → save → verify → recover"
}
```

## Notes

Don't promise zero downtime: the docs say a few seconds of registration gap, and
a longer `FAIL_WAIT` window if the provider side is changed first.
