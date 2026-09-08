---
id: J13
title: No public extension — agent can't transfer
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/maintenance.md, connect_elevenlabs/docs/agents.md]
---

## Post

The caller asks for a human. The agent says it can't transfer anyone. Your log says **"no public extension"** — and you have twenty extensions configured. 🙋

Configured isn't the same as offered. The `is_published` flag on `connect.twilio.exten` controls which extensions the AI is even told about: only **published** ones appear in the `{{available_extensions}}` dynamic variable that the conversation-initiation webhook fills per call, and only those are valid targets for the `transfer_to_exten` tool.

The fix is one checkbox — mark the target extension as **Published** — but the default is deliberate. An agent that can dial any internal extension is an agent that can put a customer through to the server room.

Publish the ones a caller should be able to reach. Leave the rest invisible.

How do you decide what an AI agent is allowed to reach? 👇

#Odoo #ElevenLabs #VoiceAI

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · ElevenLabs",
  "headline": "Configured is not",
  "headline_grad": "the same as offered.",
  "lede": "Only extensions flagged *Published* reach the agent's `{{available_extensions}}` variable — the rest stay invisible to the AI.",
  "nodes": [
    {"t": "connect.twilio.exten", "s": "is_published = True", "c": "app"},
    {"t": "transfer_to_exten tool", "s": "the only valid transfer targets", "c": "purple"}
  ],
  "link_label": "initiation webhook",
  "footer": "Default is unpublished on purpose — nobody gets transferred to the server room"
}
```

## Notes

`is_published` is re-added to `connect.twilio.exten` by `connect_elevenlabs`
(ADR-046), so it only exists where that module is installed.
