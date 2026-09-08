---
id: E03
title: Write your own summary prompt
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/admin/core-setup.md]
---

## Post

"AI call summaries are useless — they just retell the call." Usually true. Usually because nobody changed the prompt. 🎛️

In **Oduist Connect** the summary prompt is a plain settings field. The default is literally *"Summarise this phone call"* — and it's yours to replace:

🧾 A collections team asks for the promised payment date and the stated reason
🛠️ Support asks for the product, the symptom and whether it was resolved
💼 Sales asks for objections, budget signals and the agreed next step
🌍 Multilingual teams ask for a summary in one working language, whatever the call language was
🧠 The model is configurable too — GPT-5.4 mini by default, GPT-4o still available

Same transcript, completely different output — because you decided what a "summary" means in your business.

What three things would your prompt demand from every call? 👇

#Odoo #AI #PromptEngineering #CRM #OpenAI

## Card

```json
{
  "template": "comparison",
  "accent": "purple",
  "kicker": "Oduist Connect · AI",
  "headline": "Stop reading",
  "headline_grad": "generic AI summaries.",
  "lede": "The summary prompt is a *settings field*. Replace the default and every call is summarized on your terms.",
  "columns": ["Default prompt", "Your prompt"],
  "rows": [
    {"f": "Retells the conversation", "m": ["✓", "✓"]},
    {"f": "Promised payment date", "m": ["—", "✓"]},
    {"f": "Objections & budget signals", "m": ["—", "✓"]},
    {"f": "Agreed next step", "m": ["—", "✓"]},
    {"f": "Always in one language", "m": ["—", "✓"]},
    {"f": "Choice of OpenAI model", "m": ["✓", "✓"]}
  ],
  "footer": "Summary Prompt & Summary Model · Connect ▸ Configuration ▸ Settings"
}
```

## Notes

The example prompts (collections / support / sales) are illustrations of a free-text
field, not shipped presets — phrase replies accordingly.
