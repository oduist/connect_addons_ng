---
id: J14
title: TTS silently falls back to robotic Say
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md, connect_elevenlabs/docs/maintenance.md]
---

## Post

You bought a premium voice. Your IVR greets callers like a 2011 satnav. 🤖

That's the fallback working exactly as designed — and it's silent, which is why it's confusing. When ElevenLabs TTS is enabled, call-flow prompts and voicemail greetings are generated as MP3 files and `<Play>`-ed by Twilio. On **any error**, or when the integration is off, the call flow falls back to plain Twilio `<Say>`. The call never fails. It just sounds cheap.

Three things to check, in order: the integration is actually enabled, a **Selected Voice** is set in the settings, and the API key is clean (a stray space in a pasted key is a classic — re-paste it). Then hit **REGENERATE PROMPTS**.

Prompt files regenerate whenever the text changes, so a prompt edited while the key was broken stays robotic until you re-run it.

Which "graceful degradation" fooled you longest? 👇

#Odoo #ElevenLabs #IVR

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · ElevenLabs",
  "headline": "Nothing failed.",
  "headline_grad": "It just sounds cheap.",
  "lede": "Any TTS error falls back to Twilio `<Say>` instead of dropping the call — check these four before blaming the voice.",
  "tiles": [
    {"sym": "OFF", "nm": "Integration disabled", "c": "core"},
    {"sym": "VOICE", "nm": "No Selected Voice", "c": "core"},
    {"sym": "KEY", "nm": "Stray space in API key", "c": "magenta"},
    {"sym": "↻", "nm": "Regenerate prompts", "c": "purple", "hero": true},
    {"sym": "MP3", "nm": "TTS file per prompt", "c": "app"},
    {"sym": "SAY", "nm": "The fallback you hear", "c": "provider"}
  ],
  "footer": "Call-flow prompt · invalid input · voicemail greeting — each gets its own file"
}
```

## Notes

Causes come from the maintenance troubleshooting table; the `<Play>` / `<Say>`
fallback mechanics are the *Text-to-speech files* section of `agents.md`.
