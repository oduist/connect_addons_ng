---
id: A08
title: The Odoo telephony buyer's checklist
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/security.md, connect/docs/admin/licensing.md, connect/docs/user/business-records.md, connect/docs/user/recordings.md, connect_twilio/docs/installation.md, docs/index.md]
---

## Post

Eight questions that separate a real Odoo phone system from a dial button. Ask them before you sign anything. 📋

1️⃣ **Can I change carrier later?** Or is my call history welded to one vendor's API?
2️⃣ **Can two carriers run in one database** — sales on one, support on another?
3️⃣ **Does it work with the PBX I already own**, or is this a migration project in disguise?
4️⃣ **Where do recordings live** — the vendor's cloud, my bucket, or my server?
5️⃣ **Are transcripts and summaries included**, and do they survive the audio being deleted?
6️⃣ **Do calls link themselves** to leads, tickets, orders, invoices, tasks and employees?
7️⃣ **What do non-telephony users see?** A proper access group, or the app in everyone's menu?
8️⃣ **Can I read the source, and what happens when the licence lapses?**

**Oduist Connect** answers those in the docs, not in a sales call: source-available under BSL 1.1, a 30-day production trial per module, three security groups, and a provider-agnostic core.

Which question would kill your current setup? 👇

#Odoo #Telephony #VoIP #Procurement #CTI

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Checklist",
  "headline": "Ask your vendor",
  "headline_grad": "these eight first.",
  "lede": "Lock-in, hosting, recordings, transcripts, record linking, access rights, licence. *If the answers aren't in the docs, that's the answer.*",
  "tiles": [
    {"sym": "01", "nm": "Carrier lock-in", "c": "core"},
    {"sym": "02", "nm": "Two carriers, one DB", "c": "provider"},
    {"sym": "03", "nm": "Keep your PBX", "c": "provider"},
    {"sym": "04", "nm": "Where recordings live", "c": "cyan"},
    {"sym": "05", "nm": "Transcripts included", "c": "purple"},
    {"sym": "06", "nm": "Records link back", "c": "app"},
    {"sym": "07", "nm": "Access groups", "c": "core"},
    {"sym": "08", "nm": "Source & licence", "c": "memory"},
    {"sym": "09", "nm": "Odoo 17 / 18 / 19", "c": "cyan", "hero": true}
  ],
  "footer": "Source-available under BSL 1.1 · 30-day production trial per module"
}
```

## Notes

The pillar article is planned as 20 questions; the post deliberately ships
eight so every one of them is backed by a doc page. Don't claim "we answer yes
to all 20" until the full list exists. The card carries a ninth tile
(Odoo 17/18/19) because the thesis grid needs 6 or 9 tiles.
