---
id: D12
title: Choosing the LLM for your voice agent
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md]
---

## Post

"So which model is it built on?" — the question every technical buyer asks, usually expecting a one-word answer they're stuck with. 🧩

In **Oduist Connect**, the model is a field on the agent. Per agent.

🤖 Pick OpenAI GPT, Google Gemini, Anthropic Claude, or an ElevenLabs-hosted open model — `gpt-5.2` is just the default
🌡️ **Temperature** 0.0–1.0: tighten a booking agent, loosen a receptionist
✂️ **Max Tokens** caps the prediction length, or `-1` for no cap
🎚️ Voice, TTS model, stability and speed are separate settings on the same tab — reasoning and speaking are tuned independently
🧪 Out-of-range values are rejected on save, not discovered on a live call

So your after-hours receptionist and your sales-order agent don't have to share a model, a temperature, or a personality. And when the model landscape shifts again next quarter, it's a dropdown, not a migration.

Which model would you put on the phone with your customers — and why? 👇

#Odoo #VoiceAI #LLM #AIAgents

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · LLM Choice",
  "headline": "One agent, one model.",
  "headline_grad": "Your choice, per agent.",
  "lede": "GPT, Gemini, Claude or an ElevenLabs-hosted open model — plus *temperature and a token cap* on every agent.",
  "tiles": [
    {"sym": "GPT", "nm": "OpenAI", "c": "purple", "hero": true},
    {"sym": "Gem", "nm": "Google Gemini", "c": "provider"},
    {"sym": "Cl", "nm": "Anthropic Claude", "c": "memory"},
    {"sym": "Op", "nm": "Open model", "c": "app"},
    {"sym": "T°", "nm": "Temperature", "c": "cyan"},
    {"sym": "Max", "nm": "Token cap", "c": "magenta"}
  ],
  "footer": "Per-agent LLM · temperature 0.0–1.0 · max tokens or -1 for no cap"
}
```

## Notes

`gpt-5.2` is the documented default in `connect_elevenlabs/docs/agents.md`;
re-check it against the module before publishing, since the model list moves.
The call limits (max duration, concurrency, daily cap) are a separate topic —
keep them for D18.
