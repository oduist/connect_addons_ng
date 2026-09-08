---
id: K05
title: Customizing generated FreeSWITCH XML from Odoo
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

Generated configuration is wonderful — right up to the day you need the one thing the generator doesn't do. Then it's a wall. 🧱

So in Oduist Connect the FreeSWITCH XML generator is not a black box. It's twelve Jinja2 templates you can open and edit in Odoo:

📄 `directory_user`, `dialplan_user_bridge`, `dialplan_ivr`, `dialplan_ring_group`, `dialplan_inbound_did`, `dialplan_outgoing_route`, `config_sofia`, `config_acl` and friends
🧪 Every template form documents the **Jinja2 variables** available to it
📚 A **Default Template** tab sits next to your edit, so the factory version is always one click away
🏷️ Customized templates are flagged in the list — no mystery drift
↩️ **Reset to Default** when the experiment goes badly

And because the XML is served to FreeSWITCH over mod_xml_curl on demand, an edited template applies to the next call. No file to copy, no container to restart.

Would you rather edit a template, or file a feature request? Honest answers welcome. 👇

#Odoo #FreeSWITCH #Jinja2 #VoIP #Dialplan

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "The dialplan generator",
  "headline_grad": "is not a black box.",
  "lede": "Twelve editable Jinja2 templates in Odoo produce the XML FreeSWITCH executes — *with a Reset to Default button.*",
  "nodes": [
    {"t": "Jinja2 template in Odoo", "s": "documented variables · Customized flag", "c": "app"},
    {"t": "FreeSWITCH XML", "s": "directory · dialplan · sofia · ACL", "c": "provider"}
  ],
  "link_label": "mod_xml_curl",
  "footer": "Edited templates apply on the next call — no restart, no files on the host"
}
```

## Notes

Template customization is a Connect-admin feature; a broken template breaks call
routing until Reset to Default is pressed. Worth saying if someone asks about risk.
