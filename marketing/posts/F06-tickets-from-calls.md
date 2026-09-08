---
id: F06
title: Support tickets created from calls
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_helpdesk/docs/configuration.md]
---

## Post

Support tickets get logged when the queue is quiet. Which is exactly when there's nothing to log. 🎫

**Oduist Connect Helpdesk** creates the ticket from the call itself:

🎚️ Independent rules per direction — answered calls, unanswered calls, and (incoming only) callers who match no contact
👥 A default team and a default assignee, overridden by the PBX user who actually answered
🏷️ The ticket is named after the contact, falling back to the external number, which is stored on the ticket
🔗 While the call is live, an existing open ticket for that number is attached instead — no duplicate for an ongoing issue
🤖 When the AI summary is generated, it's posted to that ticket's chatter automatically

Internal calls between colleagues never create tickets, and a call that already has one is skipped.

Your night-shift callers: tickets, or voicemail nobody plays back? 👇

#Odoo #Helpdesk #CustomerService #Telephony #Automation

## Card

```json
{
  "template": "thesis",
  "kicker": "Oduist Connect · Helpdesk",
  "headline": "The call ends.",
  "headline_grad": "The ticket exists.",
  "lede": "Auto-creation runs *after the call fully ends*, so answered and missed are classified reliably — then the AI summary lands in the ticket chatter.",
  "tiles": [
    {"sym": "☎", "nm": "Answered", "c": "app"},
    {"sym": "✗", "nm": "Missed", "c": "core"},
    {"sym": "?", "nm": "Unknown caller", "c": "memory"},
    {"sym": "🎫", "nm": "Ticket", "c": "cyan", "hero": true},
    {"sym": "👥", "nm": "Team", "c": "provider"},
    {"sym": "🤖", "nm": "AI summary", "c": "purple"}
  ],
  "footer": "Open tickets are re-used, not duplicated · internal calls are ignored"
}
```

## Notes

Requires Odoo Enterprise Helpdesk. All auto-create master toggles are off by
default.
