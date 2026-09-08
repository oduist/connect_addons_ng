---
id: D10
title: "Last time you called about…" — conversation continuity
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md, connect_elevenlabs/docs/maintenance.md]
---

## Post

"Last time you called about the damaged pump on S00042 — is this the same thing?"

Nobody typed that into a prompt. The agent was handed it. 🧠

Most voice agents are amnesiacs: every call starts from zero, and the customer pays for it in repeated explanation. **Oduist Connect** closes that loop:

📼 When a call ends, ElevenLabs posts the conversation back to Odoo — transcript and summary land on the call's recording
🧾 On the next call, that summary is injected as `{{previous_topics}}`
🧩 The block is added to the system prompt at build time, then filled per call by the conversation-initiation webhook
📵 No copy-paste, no separate CRM note to maintain — it's the same call ledger your team already reads
🔁 And the transcript ElevenLabs already produced isn't re-transcribed by OpenAI. You don't pay twice for the same audio.

Continuity isn't a bigger model. It's remembering to pass what you already have.

Does your CRM actually tell the next person what the last call was about? 👇

#Odoo #VoiceAI #CX #AIAgents

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Continuity",
  "headline": "Call two starts",
  "headline_grad": "where call one ended.",
  "lede": "The previous conversation's summary is injected as *{{previous_topics}}* at call setup — the caller explains nothing twice.",
  "bubbles": [
    {"side": "left", "who": "Caller · second call", "text": "\"Hi, it's about my order again...\""},
    {"side": "right", "who": "AI Agent", "text": "\"Last time you called about the damaged pump on S00042 — is this the same thing, or something new?\""}
  ],
  "badge": "✓ summary carried over from the previous call",
  "footer": "Post-call transcript & summary on the call record · reinjected next time"
}
```

## Notes

`{{previous_topics}}` is one of two blocks the module appends to the prompt at
build time (the other lists `{{available_extensions}}`). This is ElevenLabs
per-call context — it is not the `connect_memory` module.
