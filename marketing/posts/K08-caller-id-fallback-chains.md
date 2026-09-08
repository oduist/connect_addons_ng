---
id: K08
title: Caller ID fallback chains explained
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_twilio/docs/users-and-sip.md, specs/decisions/058-caller-id-fallback.md, connect_freeswitch/docs/admin/freeswitch-setup.md]
---

## Post

An empty caller ID is not neutral. Leave it blank on Twilio and Twilio invents a number for you — the callee sees it, and so does your call ledger. 🕵️

So every outbound call in Oduist Connect walks a documented ladder until something answers:

📇 **Twilio**: the user's extension → their own outgoing caller ID → the system default caller ID → their client identity. Extension first, because a colleague should see *you*, not a DID
☎️ **FreeSWITCH**: the user's outgoing caller ID → the system default → the extension. DID first, because this ladder is about what the PSTN sees
🚫 On FreeSWITCH the caller-ID **name** is deliberately blank outbound — internal names are nobody's business outside the company
🌐 Same resolution for click-to-call, desk phones and the browser softphone

Two providers, two orders, one rule: no call ever leaves with an empty From.

Would you present the extension or the DID to an internal colleague? Genuinely split on this. 👇

#Odoo #Twilio #FreeSWITCH #VoIP #CallerID

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Caller ID",
  "headline": "Two ladders,",
  "headline_grad": "never an empty From.",
  "lede": "Order in which the outbound caller ID is resolved. *A blank caller ID lets the carrier invent one* — so there is always a last resort.",
  "columns": ["Twilio", "FreeSWITCH"],
  "rows": [
    {"f": "User's extension", "m": ["1st", "3rd"]},
    {"f": "User's outgoing caller ID", "m": ["2nd", "1st"]},
    {"f": "System default caller ID", "m": ["3rd", "2nd"]},
    {"f": "Client identity (last resort)", "m": ["4th", "—"]},
    {"f": "Caller-ID name sent outbound", "m": ["—", "blank"]},
    {"f": "Applies to click-to-call & softphone", "m": ["✓", "✓"]}
  ],
  "footer": "ADR-058 · one resolver shared by the dialplan and the REST originate"
}
```

## Notes

The Twilio ladder is `connect.user.twilio_caller_id()` (ADR-058); the FreeSWITCH
one is documented under "Outbound Caller ID (DID)". Do not describe them as a
single shared implementation — they are separate per ADR-031.
