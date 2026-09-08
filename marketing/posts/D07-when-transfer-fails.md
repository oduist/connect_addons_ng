---
id: D07
title: When the transfer fails — what a good AI agent does next
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

Here's where most voice agents quietly fail: nobody picks up the transfer. ⚠️

The caller gets silence, a dial tone, or a cheerful "goodbye!" — and you've just annoyed someone who was already asking for a human.

How **Oduist Connect** agents are specified to behave instead:

🚫 No registered SIP or web phone on the other end? The agent doesn't attempt a doomed transfer — it offers to register the request
📵 Transfer attempted but the colleague is busy, declines, or doesn't answer? The agent **says so**, comes back to the conversation, and offers to register the request
📝 On Telnyx, "Register Call Request" is always available: the qualified reason, the context and the agreed next step are written as an internal note on that call
🔇 What it never does: leave the caller waiting in silence

The failure path is the product. Anyone can demo the happy path.

What's your worst experience of being transferred into a void? 👇

#VoiceAI #Odoo #CustomerService #AIAgents

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Failure Paths",
  "headline": "Nobody picked up.",
  "headline_grad": "Now what?",
  "lede": "A busy or unregistered colleague is not a dead end — the agent comes back, *says what happened*, and records the request.",
  "bubbles": [
    {"side": "right", "who": "AI Agent", "text": "\"I tried Marta, but she's on another call right now.\""},
    {"side": "right", "who": "AI Agent", "text": "\"I've noted your request — damaged pump on S00042, replacement this week — on the call record so she has it in front of her when she rings you back.\""}
  ],
  "badge": "✓ request logged as an internal note on the call",
  "footer": "No silent hold · no dropped caller · the ask survives the failed transfer"
}
```

## Notes

Wording follows `connect/docs/user/ai-agents.md`: the agent "offers to register
the request rather than disconnecting you". Keep it as designed behaviour of the
shipped prompts, not a guarantee about arbitrary custom prompts.
