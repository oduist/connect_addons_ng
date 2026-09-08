---
id: J06
title: Inbound DID 404 and the leading plus
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

"Inbound call dropped with 404 — must be the `+` in front of my DID." 📵

Almost everyone's first guess, and on FreeSWITCH it's the wrong one. Inbound DID matching in Oduist Connect **tolerates an optional leading `+` in both directions**: a number stored as `+41215121140` matches a trunk that delivers `41215121140`, and vice versa. You do not need to mirror the trunk's exact E.164 or national format under **Connect → FreeSWITCH → Numbers**.

So if it still 404s, the *digits* differ. Look at the `destination_number` your trunk actually sends — Odoo's debug log, or `fs_cli` at debug level — and match the stored DID to it. Anything beyond a leading `+`, like an extra national prefix, is not normalized.

Five minutes of reading the real digits beats an hour of guessing formats.

What does your carrier deliver — E.164, national, or something creative? 👇

#Odoo #FreeSWITCH #SIP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · FreeSWITCH",
  "headline": "The plus is fine.",
  "headline_grad": "The digits aren't.",
  "lede": "DID matching normalizes an optional leading `+` — *nothing else*. Read the destination_number the trunk really sends.",
  "columns": ["Matches"],
  "rows": [
    {"f": "Stored +41215121140 · trunk sends 41215121140", "m": ["✓"]},
    {"f": "Stored 41215121140 · trunk sends +41215121140", "m": ["✓"]},
    {"f": "Stored +41215121140 · trunk sends 0041215121140", "m": ["—"]},
    {"f": "Stored +41215121140 · trunk sends 0215121140", "m": ["—"]},
    {"f": "Same digits, only the leading + differs", "m": ["✓"]}
  ],
  "footer": "Check the delivered digits in the Odoo debug log or fs_cli"
}
```

## Notes

The plan title framed this as "the leading + problem"; the doc says the opposite
— the `+` **is** normalized, and a remaining 404 means the digits themselves
differ. The post is written to correct that misconception on purpose.
