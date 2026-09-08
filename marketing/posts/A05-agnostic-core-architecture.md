---
id: A05
title: One phone system, nine providers — the architecture
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [specs/architecture.md, docs/index.md, connect_twilio/docs/installation.md]
---

## Post

Nine telephony providers. One `connect.call` table. That is the whole architectural idea. 🧱

**Oduist Connect** splits every integration in two:

🧩 **Shared ledger, in the core** — calls, channels, recordings, messages, PBX users, settings. Provider modules extend these models; they never redefine them. The core imports no vendor SDK and knows nothing about SIDs or TwiML.
🔌 **PBX configuration, owned per provider** — numbers, extensions, call flows, caller IDs and endpoints live in `connect.twilio.*`, `connect.freeswitch.*`, `connect.telnyx.*` and friends. Each telephony system keeps its own numbering plan.
🎛️ **Dispatchers, not hard-wiring** — click-to-call and message sending resolve the provider per user, then chain through `super()`.

So several carriers really can run in one database: sales on one, support on another, the same call history for both.

And OpenAI transcription sits in the core — any provider's recording gets a transcript and a summary.

Would your stack survive swapping the carrier? 👇

#Odoo #SoftwareArchitecture #Telephony #OpenSource

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Architecture",
  "headline": "Agnostic core.",
  "headline_grad": "Providers plug in.",
  "lede": "One shared call ledger; every numbering plan owned by its own provider module. *Swap the carrier, keep the history.*",
  "nodes": [
    {"t": "connect", "s": "calls · channels · recordings · messages", "c": "core"},
    {"t": "Provider modules", "s": "Twilio · Telnyx · FreeSWITCH · Asterisk · 3CX · Infobip · Bird · Vonage · LiveKit", "c": "provider"}
  ],
  "link_label": "_inherit",
  "footer": "Per-user provider selection · co-installation supported"
}
```

## Notes

The planned title said "eleven providers". Counting the provider modules in
`docs/index.md` gives **nine** telephony providers (Twilio, Telnyx, FreeSWITCH,
Asterisk, 3CX, Infobip, Bird, Vonage, LiveKit); ElevenLabs, Dograh and Pipecat
are AI-agent modules, not carriers. The post uses nine — adjust the count if
another provider module ships before publishing.
