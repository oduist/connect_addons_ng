---
id: J15
title: Phantom active calls and the reconcile cron
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_asterisk/docs/admin/asterisk-setup.md]
---

## Post

Three calls have been "in progress" since Tuesday. Nobody is talking. 👻

Event-driven CTI has one structural weakness: it learns that a call ended from a Hangup event. Lose that event — agent restart, AMI reconnect, a network blip — and the call sits in the ledger forever, looking active.

So Oduist Connect for Asterisk doesn't rely on the event alone. The sidecar agent reconciles against **`CoreShowChannels` once a minute** and emits synthetic hangups for channels Asterisk no longer knows about. Stale active calls heal themselves within 60 seconds, without anyone opening a shell.

If they don't heal, the agent isn't running or isn't connected: `docker logs connect-asterisk-agent`, then `asterisk -rx "manager show connected"`. The settings status fields refresh from agent heartbeats every 60 s, so a stale status there tells you the same story.

How does your integration handle a lost hangup event? 👇

#Odoo #Asterisk #CTI

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · Asterisk",
  "headline": "A lost Hangup event",
  "headline_grad": "shouldn't be forever.",
  "lede": "The sidecar agent polls *CoreShowChannels* every minute and emits synthetic hangups for channels Asterisk no longer has.",
  "nodes": [
    {"t": "Asterisk AMI", "s": "CoreShowChannels · every 60 s", "c": "provider"},
    {"t": "Odoo call ledger", "s": "stale active calls closed automatically", "c": "app"}
  ],
  "link_label": "reconcile",
  "footer": "Agent heartbeats refresh the settings status fields every 60 s"
}
```

## Notes

The doc states the reconcile behaviour in one line ("Stale active calls are
healed automatically…"); there is no literal error string for this symptom, so
the post opens on the observed state instead of a quoted message.
