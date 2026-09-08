---
id: D08
title: Ground your voice agent in your own documents
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_elevenlabs_knowledge/docs/knowledge-base.md]
---

## Post

"It'll make things up." That's the first objection to every voice agent — and it's fair, if the agent has nothing but a prompt. 📚

**Oduist Connect** grounds it in your documents instead, managed from Odoo under Connect ▸ ElevenLabs ▸ Knowledge:

📄 Upload a file (.pdf, .docx, .txt, .md, .html, .epub), point at a URL, or paste plain text
🔄 Saving the record *is* the upload — no separate push button
🚦 Each document moves draft → creating → **active**, or lands in **error** with the reason and a Retry button
✅ Only **active** documents reach the agent. Draft or errored ones are silently skipped — a half-uploaded price list can't be quoted at a customer
🔗 Attach documents on the agent's Knowledge Base tab; the affected agents re-sync automatically
👁️ Every document shows which agents use it, so you know the blast radius before you edit or delete

Your policies, your spec sheets, your terms — the same ones your staff read.

What document would your callers most want the agent to actually know? 👇

#Odoo #VoiceAI #KnowledgeBase #AIAgents

## Card

```json
{
  "template": "diagram",
  "accent": "purple",
  "kicker": "Oduist Connect · Knowledge",
  "headline": "Your documents in.",
  "headline_grad": "No invention out.",
  "lede": "PDF, DOCX, URL or plain text — managed in Odoo. Only documents in the *active* state ever reach the agent.",
  "nodes": [
    {"t": "Your docs", "s": "PDF · DOCX · URL · text", "c": "app"},
    {"t": "Voice agent", "s": "answers from them", "c": "purple"}
  ],
  "link_label": "Connect",
  "footer": "draft → creating → active · errored docs skipped · agents auto re-synced"
}
```

## Notes

Allowed file extensions are enforced by a model constraint — anything outside
`.epub .pdf .docx .txt .html .md` raises a validation error. Deleting a document
still used by an agent fails unless **Force Delete** is ticked.
