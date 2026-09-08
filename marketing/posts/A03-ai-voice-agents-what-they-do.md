---
id: A03
title: AI voice agents for Odoo — what they actually do
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md, connect_elevenlabs/docs/agents.md, connect_livekit/docs/admin/livekit-setup.md]
---

## Post

"Can it actually *do* anything, or does it just talk?" — fair question. 🤖

Here is what an AI voice agent in **Oduist Connect** does on a live call:

🔎 Recognises the caller — but only when exactly one Odoo contact matches the number, and it still asks the caller to confirm the name. Two matches and it refuses to guess.
🗣️ Opens in that contact's language, and may follow if the caller clearly switches.
📅 Calls back into Odoo through tools: create a contact for an unknown caller, list free slots, book or cancel a meeting.
🙋 Warm-transfers to a human — it collects the reason, briefs the employee privately, then bridges the same call. If nobody answers, it comes back and offers to log the request instead of leaving you in silence.
📝 Hangs up, and the call is in Connect → Calls with recording, transcript and summary.

Engines you can point at it: ElevenLabs, Telnyx AI Assistants, LiveKit Agents, Pipecat, Dograh.

What would you have it handle first? 👇

#VoiceAI #Odoo #AI #Telephony #CX

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · AI Agents",
  "headline": "It doesn't just talk.",
  "headline_grad": "It writes to Odoo.",
  "lede": "Caller lookup, calendar booking and warm transfer to a human — *as tools that call straight into your database*.",
  "bubbles": [
    {"side": "left", "who": "Caller", "text": "\"Can someone come out on Thursday morning?\""},
    {"side": "right", "who": "AI Agent", "text": "\"Thursday 9:30 or 11:00 are free with Marc. Shall I book the 9:30 and send you the confirmation?\""}
  ],
  "badge": "✓ Meeting created in the Odoo calendar",
  "footer": "ElevenLabs · Telnyx AI · LiveKit Agents · Pipecat · Dograh"
}
```

## Notes

The calendar tools ship with the ElevenLabs module. LiveKit agents expose
contact / CRM / helpdesk tools instead — don't promise calendar booking on a
LiveKit-only deployment.
