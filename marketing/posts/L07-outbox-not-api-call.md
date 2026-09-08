---
id: L07
title: Odoo never calls the AI engine
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory/docs/admin/memory-setup.md, specs/connect_memory.md]
---

## Post

Every "AI inside your ERP" demo hides the same line in the architecture: an outbound call from your production database to somebody else's model. 🕳️

**Oduist Connect Memory** inverts it. Odoo is strictly an event emitter — it never calls a memory engine.

📤 Business events become an engine-neutral JSON envelope in `connect.memory.outbox`
📥 Questions go the other way, as a pending row in `connect.memory.inbox`
🔄 A sidecar you run **pulls**: fetch, ack, claim a question, write the answer back. Four HTTP routes, authenticated with a shared token
🚫 Odoo initiates nothing outbound — so no API key, no egress and no third-party latency inside a business transaction
🧹 A retention cron drops the payload of sent rows and keeps a de-dup tombstone: the memory lives in the engine, the outbox is only a transport buffer

Pull, never push. It makes the privacy story auditable instead of contractual.

Would your security team sign off faster on push or on pull? 👇

#Odoo #AI #Architecture #Privacy #Integration

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "Odoo writes rows.",
  "headline_grad": "It never calls out.",
  "lede": "An engine-neutral envelope lands in the outbox; a sidecar you control *pulls* it and acks.",
  "nodes": [
    {"t": "Odoo", "s": "outbox · inbox · no egress", "c": "app"},
    {"t": "Your sidecar", "s": "fetch · ack · answer", "c": "memory"}
  ],
  "link_label": "pull, never push",
  "footer": "4 routes · shared-token auth · payload vacuumed after retention"
}
```

## Notes

Pairs with I12 (same architecture, deployment angle). If both run in the same
week, publish I12 second and lead it with the gateway/residency framing.
