---
id: G19
title: A softphone that survives a suspended tab
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect/docs/user/getting-started.md]
---

## Post

The single most common browser-phone support ticket: *"I came back from lunch and the phone was dead."* 💤

It isn't the phone. It's the browser. Modern browsers throttle and suspend background tabs to save battery — and a WebRTC connection is exactly the kind of thing they quietly drop. The user notices hours later, after the calls they didn't get.

The **Oduist Connect** softphone is built for that reality:

🔌 The widget reconnects on its own when the connection drops
🙈 A tab suspended in the background comes back without throwing an error dialog across your Odoo session
🟢 A status badge tells you the truth at a glance — Registered (green), Disconnected (grey), Error (red)
🗂️ Keypad, Contacts, Calls and Favourites in one panel in the navbar, so the phone lives where the work does
🎯 No desktop client to install, update or debug on 40 machines

A browser phone is only as good as its worst reconnect. That's the part we spent the time on.

How often does your team reload the page to "fix the phone"? 👇

#Odoo #WebRTC #Softphone #VoIP #Telephony

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Softphone",
  "headline": "Back from lunch.",
  "headline_grad": "Phone still alive.",
  "lede": "Browsers suspend background tabs. The widget *reconnects on its own* — no error dialog, no page reload.",
  "columns": ["Before", "Connect"],
  "rows": [
    {"f": "Phone dies with the suspended tab", "m": ["✓", "—"]},
    {"f": "Error dialog interrupts Odoo", "m": ["✓", "—"]},
    {"f": "Reload the page to get calls back", "m": ["✓", "—"]},
    {"f": "Silent reconnect when you return", "m": ["—", "✓"]},
    {"f": "Status badge shows the real state", "m": ["—", "✓"]}
  ],
  "footer": "In the Odoo navbar · keypad · contacts · calls · favourites"
}
```

## Notes

Suspended-tab reconnect without an error dialog is documented for the Telnyx
widget; automatic reconnect and the status badge are documented for FreeSWITCH.
"Before" describes the pre-fix behaviour of our own widget, not a competitor.
