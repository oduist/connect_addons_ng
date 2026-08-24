# Maintenance

## Scheduled jobs

| Cron | Model / Code | Interval | Purpose |
|------|--------------|----------|---------|
| **Fetch Call Prices from Twilio** | `connect.call` → `fetch_call_prices_batch()` | every 5 minutes | Fetches per-call cost from the Twilio REST API for completed calls that have not been priced yet. |

The job is always scheduled, but it only does work when **Fetch Call Prices** is
enabled in [settings](configuration.md#options). Twilio populates call prices
asynchronously after a call ends, which is why this runs as a deferred batch
rather than at call-completion time. Priced calls carry `price`, `price_unit`
(currency code) and `price_currency` (symbol) on `connect.call`.

To change the cadence, edit the cron under **Settings ▸ Technical ▸ Scheduled
Actions** (developer mode).

## Licensing

Twilio is a licensed Oduist module. Outbound origination calls
`oduist.license.check_license("connect")` before placing a call, so an invalid or
expired license blocks click-to-call. The `post_init_hook` refreshes the license
status on install. If click-to-call fails with a license error, verify the
`connect` license in the core settings.

## Recordings & transcription

- Twilio recording webhooks (`/twilio/webhook/recordingstatus`) create
  `connect.recording` entries; runtime start/stop from the web phone uses the
  shared softphone recording RPCs and Twilio's Recording API.
- **Transcription and summarization are not in this module.** OpenAI
  transcription (Whisper + GPT summary) lives in core `connect` because it is
  provider-agnostic. Configure it in the core settings, not here.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Sync fails with *"Error authenticating requests to the Twilio API"* | Wrong Account SID / Auth Token (Twilio error `20003`). Re-enter credentials. |
| Sync refuses to run | Account SID / Auth Token empty, or the core **API URL** is invalid. |
| Webhooks do nothing / log *"Twilio request is not valid!"* | Signature mismatch — confirm the Auth Token matches the account and that Odoo is reachable over the exact public HTTPS URL configured as **API URL**. |
| Webhooks log *"Twilio requires HTTPS to be setup!"* | Odoo is being reached over plain HTTP. Terminate TLS in front of Odoo and use an `https://` API URL. |
| Web phone will not register | Verify **API Key SID / Secret** in settings and that **Web Phone Enabled** is on for the user. |
| Outbound call raises *"User does not have a SIP username defined!"* | The user has no PBX (`connect_user`) profile / username. Fill in the Twilio user fields. |
| Call prices never appear | Enable **Fetch Call Prices**; prices arrive on the next 5-minute cron run after Twilio finalizes them. |
| Balance shows *"Balance API not available"* | The Twilio account type/region does not expose the balance endpoint; this is informational, not an error. |

### Where to look

- **Odoo server log** — webhook signature errors and Twilio API exceptions are
  logged by the `connect_twilio.controllers.twilio_webhooks` and model loggers.
- **`connect.debug`** — the core debug model records origination TwiML and other
  diagnostic traces (daily cron cleanup).
- **Twilio Console ▸ Monitor ▸ Logs** — Twilio's own call/message/error logs are
  the authoritative source for what Twilio sent and received.
