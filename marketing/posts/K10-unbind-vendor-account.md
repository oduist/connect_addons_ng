---
id: K10
title: Moving to a new vendor account safely
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/configuration.md, connect_elevenlabs/docs/webhooks-security.md]
---

## Post

Trial account becomes a company account. New workspace, new API key — and now every AI agent in Odoo is bound to IDs that no longer exist anywhere. 😬

That migration is a button in Oduist Connect, not a support ticket:

🔓 **UNBIND ACCOUNT** clears the stored `agent_uid` and tool IDs on the Odoo side and *nothing else*. Your agents, prompts, tools and transfer rules stay exactly as configured
🚫 It deliberately does **not** touch the remote account — the old workspace is left intact, so a rollback is "put the old key back"
🔑 Then paste the new API key and press **SYNC**
🔁 SYNC imports voices, regenerates the agent token, re-pushes both workspace webhooks, syncs every tool and updates every agent — in that order
🧷 The post-call webhook secret is re-created and stored with it, so signature checks keep passing

Configuration lives in Odoo. The vendor account is a binding, and bindings should be re-bindable.

Ever been locked into a vendor by a stored ID? Tell the story. 👇

#Odoo #ElevenLabs #VoiceAI #Integration #VendorLockIn

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · ElevenLabs",
  "headline": "New vendor account?",
  "headline_grad": "Unbind, then sync.",
  "lede": "UNBIND clears local agent and tool IDs only — *the remote account is untouched*, so the move is reversible.",
  "nodes": [
    {"t": "Old workspace", "s": "trial account · stale agent IDs", "c": "core"},
    {"t": "New workspace", "s": "new key · webhooks & tools re-pushed", "c": "purple"}
  ],
  "link_label": "UNBIND → SYNC",
  "accent": "purple",
  "footer": "Agents, prompts, tools and transfer rules never leave Odoo"
}
```

## Notes

UNBIND is on the ElevenLabs settings form (Connect Administrator only). SYNC is
skipped when the licence check fails — worth checking before blaming the key.
