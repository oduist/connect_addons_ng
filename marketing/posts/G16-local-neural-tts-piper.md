---
id: G16
title: Local neural TTS with Piper
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

26 languages. Zero cents per character. 🎙️

Every IVR prompt, greeting and voicemail message you play is text somebody has to turn into audio — and cloud TTS bills you for each one, forever, per character.

The **Oduist Connect** FreeSWITCH image ships **Piper**, a fast local neural TTS engine, via `mod_piper_tts`. No cloud TTS service required.

🌍 26 bundled voice models — German, French, Italian, Spanish (ES *and* MX), Polish, Portuguese (BR *and* PT), Ukrainian, Russian, Turkish, Vietnamese, Mandarin and more
🏷️ BCP-47 codes identical to the ones Twilio Say uses, so `pt-BR` and `pt-PT` really are different voices
⚡ Synthesized audio is cached with MD5 dedup — your "please hold" is generated once, ever
🔒 Prompt text never leaves your server. For some industries that's the whole argument
🧩 Called straight from the generated dialplan: `speak → piper|en-US|Hello...`

Self-hosted telephony, self-hosted voice. No metered dependency in the middle of your phone tree.

What are you paying per month to have a robot say "please hold"? 👇

#Odoo #FreeSWITCH #TTS #SelfHosted #VoIP

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Piper TTS",
  "headline": "26 neural voices.",
  "headline_grad": "No cloud bill.",
  "lede": "Piper runs *inside the FreeSWITCH image* — bundled voices, MD5-cached audio, nothing metered per character.",
  "columns": ["Cloud TTS", "Piper (local)"],
  "rows": [
    {"f": "Billed per character", "m": ["✓", "—"]},
    {"f": "Prompt text leaves your network", "m": ["✓", "—"]},
    {"f": "26 voice models in the image", "m": ["—", "✓"]},
    {"f": "Cached audio, generated once", "m": ["—", "✓"]},
    {"f": "Add your own voice model", "m": ["—", "✓"]}
  ],
  "footer": "mod_piper_tts · BCP-47 codes · called from the generated dialplan"
}
```

## Notes

26 = the bundled voice-model table in freeswitch-setup.md, counted. Cloud-TTS
column describes per-character metered pricing generally, not a named vendor —
keep it that way.
