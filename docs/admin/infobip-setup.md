# Infobip Integration

The `connect_infobip` module integrates Infobip voice calls (Calls API),
a browser WebRTC phone, SMS and WhatsApp messaging with the shared
Connect call/message ledger.

Unlike Twilio/Telnyx there is no TwiML-style markup: Infobip voice is
purely event-driven, so Odoo receives call events over webhooks and
drives the call with REST actions. This makes the webhook configuration
below essential — inbound calls do not work without it.

## Prerequisites

- An Infobip account with Voice & Video (Calls API) enabled, at least
  one voice-capable number, and — for messaging — SMS enabled and a
  registered WhatsApp sender (WABA number).
- Your **personalized base URL** (e.g. `https://xxxxx.api.infobip.com`)
  and an **API key**, both shown in the
  [Infobip portal](https://portal.infobip.com/) under the developer/API
  section.
- Odoo must be reachable from the internet over HTTPS (webhooks).

## Odoo configuration

Open **Connect → Infobip → Configuration → Settings**:

1. Enter the **Base URL** and the **API Key** (masked after saving).
2. Press **SYNC INFOBIP ACCOUNT**. The sync:
   - creates (or finds) an **"Odoo Connect" Calls configuration** and
     stores its ID — this is the voice application inbound calls are
     routed to;
   - imports your numbers into **Connect → Infobip → Numbers** and
     **Outgoing Caller IDs**;
   - pushes the per-number SMS "forward to HTTP" action to the Odoo
     inbound SMS webhook (best-effort — see Webhooks below);
   - imports WhatsApp senders and templates when WhatsApp is enabled on
     the account (failures here are non-fatal).

## Webhook security

Infobip does not sign webhooks. Instead, every webhook URL shown in the
settings form embeds a shared secret token (`?token=...`), which the
controllers verify with a constant-time comparison; requests without a
valid token get a uniform 401. The token can also be supplied as the
password of Basic Auth credentials configured on the Infobip forwarding
profile. Keep the URLs (they contain the token) out of screenshots and
logs. `Verify Infobip Requests` (Development tab) disables the check
for local testing only.

## Webhooks to configure in the Infobip portal

The settings form lists the exact URLs. Configure on the Infobip side:

| URL | Where to configure |
|-----|--------------------|
| Voice receive URL | Calls configuration → inbound call events (`CALL_RECEIVED`) |
| Voice event URL | Calls configuration → call/dialog event subscriptions |
| Inbound SMS URL | Number → SMS action "Forward to HTTP" (pushed automatically on sync when the Numbers API allows it) |
| Inbound WhatsApp URL | WhatsApp sender → inbound message forwarding |
| Delivery report URL | WhatsApp sender → delivery reports (SMS delivery reports need no setup — they use a per-message `notifyUrl`) |

Point each voice-capable number's voice action at the "Odoo Connect"
Calls configuration (the sync attempts this automatically; account
plans differ, so verify in the portal).

## Voice routing

- **Numbers** (Connect → Infobip → Numbers): set *Destination* to a
  **User** (rings their web phone and/or external phone by priority) or
  an **External Number** (forwarded; *External CallerID* controls
  whether the DID or the original caller is presented — the latter
  requires CLI passthrough entitlement on the account).
- **Users** (Connect → Users → Infobip Phone tab): enable the **Web
  Phone** (a WebRTC identity is generated automatically) and/or an
  **External Phone** in E.164, each with a priority and ring timeout.
  The external number uses Odoo's standard phone control. Ring timeouts
  run on the Infobip platform, not in Odoo.
- **Extensions** (Connect → Infobip → Extensions): short internal
  numbers pointing at users, used for web-phone dialing and click-to-call
  caller IDs. Call flows (IVR) are not part of v1.
- Unrouted or exhausted calls hear a spoken message (the user's
  voicemail prompt when enabled) and are hung up; recorded voicemail is
  not part of v1.

## Web phone and click-to-call

The web phone appears in the systray for users with the Infobip web
phone enabled (it is on by default when Infobip is the only telephony
module). Outgoing web-phone calls dial through the Calls configuration,
so extensions and caller IDs are resolved by Odoo and every call lands
in the ledger. Click-to-call from phone fields uses the per-user
*Click-to-Call Provider* = Infobip: the agent's phone rings first, then
the destination is bridged.

## Recordings and transcription

Calls to/from users with *Record Calls* enabled are recorded at the
dialog level. Recording files are downloaded by a cron with the API key
and stored as attachments; OpenAI transcription (core setting) picks
them up automatically.

## Messaging

- **SMS**: send from any record's SMS composer (sender = the user's
  Infobip outgoing caller ID) or reply from Connect → Infobip →
  Messages. Delivery reports update message status automatically.
- **WhatsApp**: register senders in the Infobip portal, then sync.
  Templates are created and submitted for Meta approval from
  Connect → Infobip → Messages → WhatsApp Templates (templates are
  per-sender at Infobip). Free-form replies require an inbound message
  within the last 24 hours; otherwise pick an approved template in the
  WhatsApp composer.
- **Message Configuration** (admin-only) maps inbound messages on a
  number to a destination model (e.g. auto-create partners).

## Known limitations (v1)

- No IVR/call flows, no recorded voicemail, no RCS/Viber, no number
  purchasing from Odoo, no call transfer from the web phone.
- Call prices are not fetched (Infobip exposes no per-call price on the
  call resource).
- The browser receives inbound calls only while a tab with the web
  phone is open (no push wake-up in the JS SDK) — use the External
  Phone ring step as a fallback.
