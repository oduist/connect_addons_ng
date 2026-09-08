---
id: G20
title: Softphone now speaks four more languages
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [docs/changelog.md, connect/docs/user/getting-started.md, connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

Your warehouse team uses Odoo in German. Your accountant uses it in Italian. And the phone widget in the corner of both screens says "Transfer". 🌍

Not any more. The **Oduist Connect** FreeSWITCH softphone now ships translated into **German, French, Italian and Russian**.

🗣️ It follows your Odoo interface language automatically — no separate setting to find
🔤 Anything else falls back to English, so nothing ever renders half-translated
📞 And it's not just the UI: call flows speak too, through 26 bundled local Piper voices, with per-user **Language** and **Voice** for greetings and voicemail prompts

Telephony is the one app where "English is fine, everyone manages" is least true. People are talking to customers while reading the interface. A button they have to translate in their head is a button they hesitate on.

The phone should speak the same language as the rest of the screen.

Which language should we translate next? 👇

#Odoo #Localization #Softphone #FreeSWITCH #Telephony

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Softphone",
  "headline": "The phone speaks",
  "headline_grad": "your language now.",
  "lede": "The FreeSWITCH softphone follows *your Odoo interface language* — with English as the safe fallback.",
  "tiles": [
    {"sym": "DE", "nm": "Deutsch", "c": "provider"},
    {"sym": "FR", "nm": "Français", "c": "provider"},
    {"sym": "IT", "nm": "Italiano", "c": "provider"},
    {"sym": "RU", "nm": "Русский", "c": "provider"},
    {"sym": "EN", "nm": "Fallback", "c": "cyan", "hero": true},
    {"sym": "26", "nm": "Piper TTS voices", "c": "app"}
  ],
  "footer": "Follows the Odoo UI language · per-user TTS language & voice"
}
```

## Notes

Shipped 2026-08 for `connect_freeswitch`. The 26 figure is the bundled Piper
voice-model list, i.e. call-flow TTS languages — distinct from the four UI
translations. Keep the two numbers clearly separate in replies.
