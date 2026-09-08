---
id: D11
title: Prompt versioning — roll back an agent that got worse
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs/docs/agents.md]
---

## Post

We've made an agent worse with a "small prompt improvement" more than once. Everybody has. The question is what happens the morning after. 🔙

In **Oduist Connect**, editing an agent's prompt is versioned automatically:

📸 Every save of the **Prompt** field snapshots the new text as `v1`, `v2`, `v3`… and marks it the active version
↩️ Pick an earlier snapshot in **Prompt Version** and its text is restored into the prompt — that's the rollback
🔄 Saving pushes the agent config straight to ElevenLabs, so the live behaviour follows the record in Odoo
📋 Reusable starting points live as **Agent Templates** — a named system prompt you copy into new agents

No spreadsheet of prompt drafts. No "which version was live last Tuesday?" in a group chat. The history is on the record.

Prompt engineering is engineering. It gets the same version control as everything else you deploy.

How do you track prompt changes today — honestly? 👇

#Odoo #VoiceAI #PromptEngineering #AIAgents

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · Prompt Versions",
  "headline": "The new prompt",
  "headline_grad": "made it worse.",
  "lede": "Every prompt edit is snapshotted as v1, v2, v3… — *roll back by picking the old version*.",
  "columns": ["Prompt in a doc", "Connect"],
  "rows": [
    {"f": "Every edit snapshotted", "m": ["—", "✓"]},
    {"f": "Numbered versions (v1, v2…)", "m": ["—", "✓"]},
    {"f": "Restore an earlier prompt", "m": ["—", "✓"]},
    {"f": "Active version visible on the record", "m": ["—", "✓"]},
    {"f": "Reusable prompt templates", "m": ["—", "✓"]},
    {"f": "Change pushed live on save", "m": ["—", "✓"]}
  ],
  "footer": "connect.elevenlabs_agent_prompt · rollback from the agent form"
}
```

## Notes

Rollback restores the *text* into the prompt field, which itself creates a new
snapshot — say "restore", not "revert history", if anyone asks in comments.
