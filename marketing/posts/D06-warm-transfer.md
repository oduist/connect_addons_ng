---
id: D06
title: How warm transfer works — the AI briefs the human first
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/ai-agents.md, connect_telnyx/docs/admin/telnyx-setup.md]
---

## Post

"Marta, it's Jan Kowalski — confirmed. Damaged pump on order S00042, he wants a replacement shipped this week. Putting him through now."

The caller never heard that. The colleague heard it before picking up the conversation. 🤝

That's a **warm transfer** in Oduist Connect, and it's the difference between an AI that deflects and one that hands over:

🗣️ The agent first asks why you're calling and collects the context
📇 It confirms the caller's name — and only when exactly one Odoo contact matches that number
🔕 It briefs the employee **privately**, with the reason, the context and the agreed next step
📞 Then it bridges the same call — no callback, no repeating yourself
📡 On Telnyx it can check SIP/WebRTC registration first, so it doesn't route to a phone that isn't there

Caveat worth saying out loud: registration means the device is reachable, not that the human will answer. Busy, declined and no-answer still happen.

How much of your first-line call time is just "let me explain again"? 👇

#Odoo #VoiceAI #Telnyx #CustomerService

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Warm Transfer",
  "headline": "The AI answers.",
  "headline_grad": "The human finishes.",
  "lede": "Before bridging, the agent briefs your colleague *privately* — name, reason, context, next step. The caller repeats nothing.",
  "nodes": [
    {"t": "Caller", "s": "hears ringback", "c": "cyan"},
    {"t": "AI Agent", "s": "private briefing", "c": "purple"},
    {"t": "Your colleague", "s": "SIP / web phone", "c": "app"}
  ],
  "link_label": "warm transfer",
  "footer": "Registration checked before transfer · same call bridged, no callback"
}
```

## Notes

Do not promise caller-side hold music: the built-in Telnyx Transfer tool has
none — the caller hears transfer progress/ringback. The Warm Transfer Message
Delay (default 2000 ms) exists so a freshly answered WebRTC leg has media before
the briefing plays.
