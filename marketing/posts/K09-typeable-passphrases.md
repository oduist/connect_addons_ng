---
id: K09
title: Passphrases a human can type into a desk phone
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [specs/decisions/022-endpoint-auth-password-passphrase.md, connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

There is one password in a phone system that a human has to type by hand, on a desk phone keypad, with no copy-paste: the SIP endpoint password. 📟

Which is exactly why it used to be the weakest one in the building. Ours was once a free-text field that would happily accept a single character.

Now the FreeSWITCH endpoint password is generated for you:

🔤 Five `word+digit` groups from a curated wordlist — `flour3-tower9-rome1-watching2-hello8`
🎲 Generated with `secrets` (a CSPRNG), never `random` — about **56 bits of entropy**
🔒 Read-only by design, so nobody can accidentally weaken it; **Regenerate** is the deliberate way to rotate
👁️ Masked in the form, with a reveal toggle for typing on a device and a copy button for everything else
🧯 The upgrade backfilled only *empty* passwords — existing ones were left untouched

Strong and dictatable over the phone. That combination is the whole point.

Random string or passphrase for credentials humans must type? 👇

#Odoo #FreeSWITCH #SIP #Security #Passwords

## Card

```json
{
  "template": "dialog",
  "kicker": "Oduist Connect · Endpoints",
  "headline": "A password you can",
  "headline_grad": "read down the phone.",
  "lede": "SIP endpoint passwords are auto-generated as five word+digit groups — *~56 bits of entropy, typeable on a desk phone keypad.*",
  "bubbles": [
    {"side": "left", "who": "Technician on site", "text": "\"I'm at the desk phone, no laptop. What's the SIP password for extension 104?\""},
    {"side": "right", "who": "Admin in Odoo", "text": "\"flour3 — tower9 — rome1 — watching2 — hello8. Hyphens between the groups.\""}
  ],
  "badge": "✓ Generated with secrets, read-only, one-click regenerate",
  "footer": "ADR-022 · reveal toggle for typing, copy button for everything else"
}
```

## Notes

The example passphrase is the one from ADR-022's documentation — it is an
illustration, not a live credential. Keep it as-is.
