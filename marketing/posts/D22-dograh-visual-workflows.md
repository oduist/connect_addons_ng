---
id: D22
title: Drag-and-drop voice workflows with Dograh
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_dograh/docs/admin/dograh-setup.md]
---

## Post

The person who knows how a call should go is almost never the person who can build a voice pipeline. So the script waits in a ticket queue. 🧩

Dograh in Oduist Connect closes that gap:

🖱️ The conversation itself is built in a drag-and-drop workflow editor — open source, self-hostable, no proprietary account required
📞 Publish the workflow, create the agent in Odoo, click Create Extension, and the agent has a number on your FreeSWITCH
🔁 Enter that same number on Dograh's Phone Numbers page and pick the inbound workflow — one mapping, two systems, both yours
🎙️ Enable Record Calls and the session lands on the Odoo call form, ready for the core transcription and GPT summary
🌍 Route a DID or an IVR choice to the extension whenever you want to expose it to the outside world

Iterating on what the agent says becomes an afternoon for the person who owns the process — not a sprint for the integrator.

Who writes your call scripts today, and who has to implement them? 👇

#Odoo #VoiceAI #OpenSource #FreeSWITCH #AI

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Dograh",
  "headline": "Draw the call flow.",
  "headline_grad": "The AI speaks it.",
  "lede": "A *drag-and-drop workflow* in Dograh answers an extension on your own FreeSWITCH — and logs into Odoo.",
  "nodes": [
    {"t": "Dograh", "s": "visual workflow builder", "c": "purple"},
    {"t": "FreeSWITCH + Odoo", "s": "extension · trunks · call log", "c": "app"}
  ],
  "link_label": "Connect",
  "footer": "Open source, self-hosted · audio over your own media path"
}
```

## Notes

Known limitation to disclose if asked in comments: transfer-to-human from a
Dograh workflow is not supported yet (`supports_transfers` is false) — the
workflow engine reports it gracefully if a transfer node is reached. Extension
numbers must be configured in both Odoo and Dograh; the number→workflow mapping
lives in Dograh.
