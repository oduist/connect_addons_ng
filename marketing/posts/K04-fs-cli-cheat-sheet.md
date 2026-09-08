---
id: K04
title: fs_cli cheat sheet for operators
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/fs_cli.md, connect_freeswitch/docs/admin/freeswitch-setup.md, connect_freeswitch/docs/admin/parking.md]
---

## Post

You can run a FreeSWITCH box for a year and only ever need about ten `fs_cli` commands. Here they are. 🛠️

📡 `sofia status` — every profile and gateway in one screen
📶 `sofia status gateway <name>` — the trunk is healthy only if State is **REGED**
♻️ `sofia profile external restart reloadxml` — the hammer, when a profile looks stuck
🔄 `reloadxml` — re-read configuration from every source, including xml_curl
🐛 `xml_curl debug_on` — the single most useful command when Odoo and FreeSWITCH disagree
🚦 `acl <ip> <list>` / `reloadacl` — is this trunk IP actually allowed?
🧩 `module_exists <name>` — e.g. `mod_valet_parking` before debugging call parking
🔍 `global_getvar <name>` and `status` — what the switch thinks it is
🅿️ `valet_info default` — which parking slots are occupied right now

With Oduist Connect you rarely need them for *configuration* — that lives in Odoo. You need them to answer "is it FreeSWITCH or is it me".

Which one is muscle memory for you? 👇

#Odoo #FreeSWITCH #SIP #VoIP #SysAdmin

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · fs_cli",
  "headline": "Ten commands",
  "headline_grad": "run a FreeSWITCH box.",
  "lede": "Configuration lives in Odoo. *fs_cli is for answering one question:* is it the switch, or is it me?",
  "tiles": [
    {"sym": "sofia", "nm": "status", "c": "provider"},
    {"sym": "gw", "nm": "REGED?", "c": "provider"},
    {"sym": "restart", "nm": "reloadxml", "c": "provider"},
    {"sym": "xml", "nm": "curl debug", "c": "cyan", "hero": true},
    {"sym": "acl", "nm": "ip allowed?", "c": "core"},
    {"sym": "reload", "nm": "acl / xml", "c": "core"},
    {"sym": "mod", "nm": "module_exists", "c": "app"},
    {"sym": "var", "nm": "global_getvar", "c": "app"},
    {"sym": "valet", "nm": "parking info", "c": "memory"}
  ],
  "footer": "Run them inside the container: fs_cli -p \"$FS_ESL_PASSWORD\" -x \"...\""
}
```

## Notes

The module's `docs/fs_cli.md` reference table lists ten commands, not eleven —
the extra ones here (`sofia status gateway`, `valet_info`, `status`) come from
the setup and parking guides. Post text says "about ten" on purpose.
