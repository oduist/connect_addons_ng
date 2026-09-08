---
id: C09
title: Video meetings in Odoo with LiveKit
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_livekit/docs/user/meetings.md, connect_livekit/docs/admin/livekit-setup.md]
---

## Post

A video call started from the customer's contact record, with the recording and its AI summary filed back onto that same customer. No third meeting tool in the middle, no "can you send me the link again". 🎥

That's **Oduist Connect + LiveKit**:

🎬 **New LiveKit Meeting** on a contact, or a room from Connect ▸ LiveKit ▸ Rooms
🔗 Every room has a public URL. Guests open it, type a display name and join — no account, no password, nothing to install. The link is unguessable, so treat it as the meeting key
⏺️ Tick **Record Meeting** and the recording lands in Connect ▸ Recordings, transcribed and summarised automatically when transcription is on
🚪 **Close Room** ends it for everyone
🏠 The whole LiveKit stack — the SFU, the SIP bridge, the recording service — runs on your own host

Your customers' faces and voices stay on infrastructure you control. That's a hard sentence to say about most meeting tools.

Where do your customer video calls live today? 👇

#LiveKit #Odoo #WebRTC #SelfHosted #VideoConferencing

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · LiveKit",
  "headline": "Meetings that start",
  "headline_grad": "on a contact card.",
  "lede": "Create the room from the customer record, send the public link — *guests join with a name, nothing else*. Recording and summary come back to Odoo.",
  "nodes": [
    {"t": "Odoo contact", "s": "New LiveKit Meeting", "c": "app"},
    {"t": "LiveKit room", "s": "self-hosted SFU + Egress", "c": "provider"}
  ],
  "link_label": "public guest link",
  "footer": "No guest account · recording in Connect ▸ Recordings · AI transcript & summary"
}
```

## Notes

All `connect.livekit.*` models are admin-only: regular Connect users get the
meeting links and the web phone, not the configuration menus. Browsers need
`wss://`, so TLS in front of port 7880 is a real prerequisite.
