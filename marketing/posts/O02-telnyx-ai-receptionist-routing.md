---
id: O02
title: Telnyx AI receptionist routing
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_telnyx/docs/admin/telnyx-setup.md, docs/changelog.md]
---

## Post

An AI receptionist that transfers a caller to a phone nobody is holding is just a slower voicemail. ☎️

The Telnyx AI assistants in **Oduist Connect** check first:

🔍 Before transferring, Odoo asks Telnyx which of that person's devices are actually registered — SIP hardphone or browser phone alike
🤝 The transfer is warm: the assistant briefs the recipient privately with the confirmed caller name, the reason, the relevant context and the agreed next step, then bridges the call
🧑‍💼 **Personal Receptionist** answers for one manager. **Company Receptionist** replaces the IVR and hands off into your department call flows — the ring users on those flows are the transfer candidates
📝 Nobody registered? It offers to register the request instead, and writes the reason and next step onto the call as an internal note
🪪 It greets a caller by name only when exactly one contact matches the number, and asks them to confirm it — duplicates are marked ambiguous, never guessed

Registration doesn't guarantee someone answers. It does guarantee you stop transferring into the void.

How does your phone menu handle "everyone's in a meeting"? 👇

#VoiceAI #Telnyx #Odoo #CustomerService #AI

## Card

```json
{
  "template": "dialog",
  "accent": "purple",
  "kicker": "Oduist Connect · Telnyx AI",
  "headline": "It checks who's",
  "headline_grad": "actually there.",
  "lede": "The assistant qualifies the caller, confirms a registered device, then *warm-transfers with a private briefing* — name, reason and next step.",
  "bubbles": [
    {"side": "left", "who": "Caller", "text": "\"I need to talk to someone about the quote you sent last week.\""},
    {"side": "right", "who": "AI Receptionist", "text": "\"Of course. May I confirm you're Ms. Kovacs? Anna handles that account and her phone is online — one moment while I bring her in.\""}
  ],
  "badge": "✓ Warm transfer · recipient briefed before the bridge",
  "footer": "Registration checked via Telnyx · personal or company receptionist"
}
```

## Notes

Time-sensitive: shipped in the 2026-08 changelog. Publish soon or drop the
"new" framing — the capability stands on its own as an evergreen post.

The card dialog is illustrative, not a transcript.
