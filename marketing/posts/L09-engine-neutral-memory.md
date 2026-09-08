---
id: L09
title: Engine-neutral customer memory
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [specs/connect_memory.md, connect_memory/docs/admin/memory-setup.md]
---

## Post

Pick your AI memory vendor this quarter and you'll rewrite the integration when you change it next year. Unless the integration never knew the vendor's name. 🔀

That's the design rule behind **Oduist Connect Memory**:

📦 Odoo writes one **engine-neutral JSON envelope** — `occurred_at`, `actor`, `text`, `facts`, `data`, `tags`, `sensitivity`, `dedup_key`, `content_hash`
🏷️ The envelope carries an *optional* `engine` field. The sidecar, not Odoo, decides how to load it
🔀 The fetch filter matches rows for a target engine **or** rows with no engine — so two engines can drain the same outbox side by side
🔌 The whole contract is four HTTP routes. A reference Hindsight gateway ships in `connect_memory/deploy/`; Cognee or your own implementation plugs into the same ones
🧩 Domain modules (sale today, more later) emit through the same mixin — swapping engines never touches them

Vendor choice becomes a container you can replace, not an architecture you're stuck with.

Which memory engine would you point it at first? 👇

#Odoo #AI #OpenSource #Architecture #ERP

## Card

```json
{
  "template": "thesis",
  "accent": "purple",
  "kicker": "Oduist Connect · Memory",
  "headline": "One envelope.",
  "headline_grad": "Any engine.",
  "lede": "The integration doesn't know your vendor's name — *four HTTP routes* are the whole contract.",
  "tiles": [
    {"sym": "Hs", "nm": "Hindsight · reference gateway", "c": "memory", "hero": true},
    {"sym": "Cg", "nm": "Cognee", "c": "memory"},
    {"sym": "You", "nm": "your own engine", "c": "purple"},
    {"sym": "env", "nm": "one JSON envelope", "c": "cyan"},
    {"sym": "4", "nm": "HTTP routes, that's it", "c": "provider"},
    {"sym": "ack", "nm": "fetch · ack · answer", "c": "app"}
  ],
  "footer": "Engine field is optional — two engines can drain one outbox"
}
```

## Notes

Only the Hindsight gateway ships as reference code. Cognee is named as a
supported target in the spec, not as a shipped adapter — don't imply otherwise.
