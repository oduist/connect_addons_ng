---
id: D14
title: Multilingual AI agent is not a prompt setting
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md]
---

## Post

Adding "answer in the caller's language" to your system prompt does not make a voice agent multilingual. 🌍

The prompt is the one layer that was never the problem. Three others have to agree:

🎙️ Speech recognition must be automatic or multilingual — not pinned to a single language
🔊 The TTS voice must actually speak those languages; an English-only voice stays English-only no matter what the LLM understands
🗣️ Language policy decides where the conversation starts: the matched contact's Odoo language, or the agent's fallback for unknown callers
🎚️ Speaking speed has to stay in the 0.5–1.5 range — outside it the agent cannot synthesise its own greeting and the call ends a second after it is answered
▶️ Play the voice sample before saving; that catches a broken voice/speed pair before your first caller does

In Oduist Connect all four live on one agent form inside Odoo, next to the contact data the agent reasons about.

Which language pair breaks your current setup first? 👇

#Odoo #VoiceAI #Multilingual #CX #AI

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "Multilingual is not",
  "headline_grad": "a prompt setting.",
  "lede": "An agent speaks a language only when *STT, voice and language policy* all support it — the prompt is the easy part.",
  "columns": ["Prompt only", "Full stack"],
  "rows": [
    {"f": "LLM understands the language", "m": ["✓", "✓"]},
    {"f": "Speech recognition set to auto", "m": ["—", "✓"]},
    {"f": "Voice can actually speak it", "m": ["—", "✓"]},
    {"f": "Greeting in the contact language", "m": ["—", "✓"]},
    {"f": "Follows a mid-call switch", "m": ["—", "✓"]},
    {"f": "Voice/speed checked before save", "m": ["—", "✓"]}
  ],
  "footer": "Voice, STT and language policy on one agent form in Odoo"
}
```

## Notes

Do not quote a language count — the core doc does not give one, and the number
depends on the chosen STT model and voice. Keep the 0.5–1.5 speed range exact;
it is a documented constraint, not a recommendation.
