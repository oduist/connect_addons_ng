---
id: I12
title: Data never leaves until you deploy the gateway
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory/docs/admin/memory-setup.md, specs/connect_memory.md]
---

## Post

The fastest way to fail an AI review: your ERP quietly POSTing customer data to a vendor's API because someone ticked a box. 🚦

**Oduist Connect Memory** is built so that can't happen. Odoo never calls a memory engine. It writes engine-neutral events into an outbox table (`connect.memory.outbox`) and questions into an inbox table — and stops there.

📦 An external **gateway that you deploy** pulls pending rows over HTTP, acknowledges them and writes answers back
🛑 No gateway running? Events simply accumulate in the outbox. Nothing leaves your database
🔑 The gateway authenticates every call with a shared token (`X-Memory-Token`, or a `token` JSON-RPC param) against exactly four routes
🎚️ A master switch — *Enable memory capture* — gates capture itself; while it's off, nothing is written at all
🧹 An outbox retention cron drops the payload of sent rows and keeps only a de-dup tombstone

Data residency becomes a deployment decision, not a vendor promise.

Where would you run that gateway — your VPC, or nowhere at all? 👇

#Odoo #AI #DataPrivacy #Architecture #ERP

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "Nothing leaves until",
  "headline_grad": "you deploy the gateway.",
  "lede": "Odoo writes an *outbox*. A gateway you run pulls it. No gateway, no egress.",
  "nodes": [
    {"t": "Odoo", "s": "outbox + inbox tables", "c": "app"},
    {"t": "Your gateway", "s": "pulls · acks · answers", "c": "memory"},
    {"t": "Memory engine", "s": "Hindsight · Cognee · yours", "c": "purple"}
  ],
  "link_label": "you deploy it",
  "footer": "4 HTTP routes · shared-token auth · master switch off by default"
}
```

## Notes

Do not claim data residency guarantees or certification — the claim is about the
architecture (pull-based, self-hosted gateway), nothing more.
