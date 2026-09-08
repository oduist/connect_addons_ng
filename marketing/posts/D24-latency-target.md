---
id: D24
title: The 1.4-second acceptance target
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_pipecat/docs/admin/pipecat-setup.md]
---

## Post

1.4 seconds. That is the acceptance target written into our Pipecat deployment guide: first agent audio, with barge-in working. ⏱️

Not a measured average. Not a benchmark. A bar a deployment has to clear before anyone calls it finished.

Why publish a target instead of a number?

📐 The target is ours; the latency is not. Provider and network latency dominate the result, so it has to be measured in your deployment, on your links
🧪 It is a two-part test on purpose: audio under 1.4 s AND the caller can talk over a long reply. Fast but uninterruptible is still a bad phone call
🎛️ The tuning surface is explicit — STT, LLM and TTS provider and model are chosen per agent, so a miss has somewhere to go
🔍 And when it misses, the diagnosis is documented: WSS or certificate failures, token mismatches, provider init errors, each with the log line to look for

Callers judge a voice agent in the first two seconds. Everything clever that happens afterwards is negotiable.

What is your honest tolerance for silence after "hello"? 👇

#Odoo #VoiceAI #Latency #Engineering #AI

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · Pipecat",
  "headline": "First audio in",
  "headline_grad": "under 1.4 seconds.",
  "lede": "The *documented acceptance target* for a self-hosted Pipecat agent — measured in your own deployment, with barge-in working.",
  "tiles": [
    {"sym": "1.4s", "nm": "First audio target", "c": "purple", "hero": true},
    {"sym": "STT", "nm": "Speech to text", "c": "provider"},
    {"sym": "LLM", "nm": "Reasoning model", "c": "magenta"},
    {"sym": "TTS", "nm": "Voice synthesis", "c": "app"},
    {"sym": "BRG", "nm": "Barge-in working", "c": "memory"},
    {"sym": "FS", "nm": "Your FreeSWITCH", "c": "core"}
  ],
  "footer": "Acceptance target, not a benchmark · measure it in your deployment"
}
```

## Notes

Critical wording rule: 1.4 s is an acceptance target from the Pipecat setup doc,
never a measured production result. The doc explicitly says provider and network
latency dominate, so any comment claiming a guaranteed number must be corrected.
