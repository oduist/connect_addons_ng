---
id: F01
title: Turn missed calls into CRM leads
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_crm/docs/configuration.md]
---

## Post

The call you didn't answer is still a lead. It just never made it into the CRM. ☎️

**Oduist Connect CRM** turns that into a rule set — seven toggles, no code:

🎚️ A master switch per direction: incoming and outgoing
✅ Per direction: create for answered calls, for unanswered calls, or both
❓ Incoming only: create even for numbers that match no contact
👤 The salesperson is the PBX user who answered, then the first user called, then your default salesperson
🏷️ Choose whether Connect creates a lead or an opportunity

Two guards we built in on purpose: creation runs only when the call has fully ended, so "missed" is never a guess mid-ring — and calls to your own colleagues never create anything.

Everything is off until you switch it on. How many of last month's unanswered calls would you want as leads? 👇

#Odoo #CRM #Sales #Telephony #LeadGeneration

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · CRM",
  "headline": "Seven toggles",
  "headline_grad": "between a call and a lead.",
  "lede": "Auto-create runs *when the call has fully ended* — so answered and missed are facts, not guesses.",
  "columns": ["Incoming", "Outgoing"],
  "rows": [
    {"f": "Master auto-create switch", "m": ["✓", "✓"]},
    {"f": "For answered calls", "m": ["✓", "✓"]},
    {"f": "For unanswered calls", "m": ["✓", "✓"]},
    {"f": "For unknown callers", "m": ["✓", "—"]},
    {"f": "Calls to colleagues", "m": ["—", "—"]},
    {"f": "Lead or opportunity", "m": ["✓", "✓"]}
  ],
  "footer": "All master toggles are off by default · a call that has a lead is never doubled"
}
```

## Notes

"Calls to colleagues" is documented as a skip for outgoing calls that reach a
local PBX user; the card row reads as "never creates" for both columns.
