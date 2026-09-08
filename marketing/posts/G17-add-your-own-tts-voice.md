---
id: G17
title: Add your own TTS voice from HuggingFace
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

"Austrian German isn't in the list." Fine — it's two files. 📦

Bundled voices are a starting point, not a ceiling. **Oduist Connect** runs Piper on your own FreeSWITCH box, and Piper voices are just model files you can add.

📥 Pick a voice from **rhasspy/piper-voices** on HuggingFace — a large public catalogue of open TTS models
🗂️ You need exactly two files: `<voice>.onnx` (the model) and `<voice>.onnx.json` (its config)
📁 Drop them into `/opt/piper/models/` in the container
🧾 Add one line to `autoload_configs/piper_tts.conf.xml`:
`<model language="de-AT" path="/opt/piper/models/de_AT-....onnx" />`
🖥️ To make the new code selectable on the call-flow form, override `_get_language_selection()` in your own extension module

That's the whole procedure. No vendor request, no waiting for a roadmap, no per-character contract for a language nobody else asked for.

Open models on your own hardware means the voice list is yours to extend.

Which language is missing from your phone system today? 👇

#Odoo #FreeSWITCH #TTS #OpenSource #SelfHosted

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Piper TTS",
  "headline": "Voice not in the list?",
  "headline_grad": "Add it yourself.",
  "lede": "Two files from *rhasspy/piper-voices*, one line of config — and your call flows speak a new language.",
  "tiles": [
    {"sym": "HF", "nm": "rhasspy/piper-voices", "c": "memory"},
    {"sym": ".onnx", "nm": "The model", "c": "cyan"},
    {"sym": ".json", "nm": "Model config", "c": "cyan"},
    {"sym": "/opt", "nm": "piper/models/", "c": "provider"},
    {"sym": "XML", "nm": "piper_tts.conf", "c": "provider"},
    {"sym": "de-AT", "nm": "New language code", "c": "app", "hero": true}
  ],
  "footer": "Override _get_language_selection() to expose it on call flows"
}
```

## Notes

`de-AT` is the example code used in the admin doc. The callflow language list is
duplicated per provider by design (ADR-031/037) — an override belongs in your
own extension module.
