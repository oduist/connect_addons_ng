---
id: L05
title: Backfill history without breaking anything
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_memory/docs/admin/memory-setup.md, connect_memory/docs/user/memory.md, specs/connect_memory.md]
---

## Post

New correspondence flows into the memory from day one. But the interesting part is the five years already sitting in your database. 📚

**Oduist Connect Memory** loads it without a migration project:

👤 **One customer** — click *Load correspondence to memory* on the contact. Their past emails and chatter messages are queued, and you get a count of what was newly added
🏢 **All customers** — Connect ▸ Configuration ▸ Memory ▸ *Backfill all partners* opens a wizard: pick a date range, preview the candidate count, start the job
🐢 It's a resumable background job drained by a cron in batches — not a request that times out at 2 000 partners
♻️ Enqueue deduplicates on a stable key plus a content hash, so clicking twice reports "0 new" instead of doubling the memory
🔐 Backfill jobs and the wizard are admin-only infrastructure

Preview first, run in batches, safe to re-run. That's the whole trick.

How much customer history is sitting unread in your Odoo right now? 👇

#Odoo #AI #DataMigration #CRM #ERP

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "Years of history,",
  "headline_grad": "loaded in batches.",
  "lede": "A resumable background job with a *preview step* — and idempotent enqueue, so re-running is free.",
  "nodes": [
    {"t": "Past emails & chatter", "s": "pick a date range, preview", "c": "cyan"},
    {"t": "Memory outbox", "s": "deduplicated, drained by cron", "c": "memory"}
  ],
  "link_label": "resumable backfill",
  "footer": "Per-contact button or admin wizard for all partners"
}
```

## Notes

"0 new" on a second click is the documented behaviour of the per-contact button;
the same dedup rule (`dedup_key` + `content_hash`) covers the bulk wizard.
