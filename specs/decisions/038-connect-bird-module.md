# 038 — Bird.com provider module (`connect_bird`)

## Status

Accepted (supersedes the first cut of this ADR that was numbered 035–037 and
targeted the legacy CRM API; 035–037 are taken by parallel provider work (infobip, vonage, TTS prompts))

## Context

Bird.com (formerly MessageBird) is added as the next messaging/voice
provider on top of the technology-agnostic `connect` core (ADR-031), next
to `connect_twilio`, `connect_freeswitch` and `connect_asterisk`.

Bird currently exposes **two API generations**:

- the legacy CRM API (`api.bird.com`, `Authorization: AccessKey`, every
  path scoped to `/workspaces/{ws}/channels/{channelId}/...`, MessageBird
  HMAC webhook signatures) documented on docs.bird.com;
- the **developer platform** (`https://{region}.platform.bird.com/v1`,
  `Authorization: Bearer bk_{region}_...`, workspace implicit in the
  key), relaunched with product-scoped paths — `/v1/email/*`,
  `/v1/sms/messages`, `/v1/voice/calls`, `/v1/whatsapp/messages`,
  `/v1/whatsapp/templates`, `/v1/numbers`, `/v1/webhooks` — and
  Standard-Webhooks event delivery. The owner's Bird account issues
  platform keys, so the platform API is the target (owner decision after
  live probing; the first implementation against the legacy CRM API was
  ported).

Platform facts confirmed live/from published references:

- SMS send: `POST /v1/sms/messages` `{to, from, text, category}` →
  `{id, status, direction, segments, cost, ...}`.
- Webhook registration: `POST /v1/webhooks` `{url, events[]}`; the
  response carries the signing `secret` (`whsec_...`) **exactly once**.
- Webhook delivery: Standard Webhooks — envelope
  `{type, timestamp, data}`, headers `webhook-id`/`webhook-timestamp`/
  `webhook-signature: v1,<base64>`, HMAC-SHA256 over
  `"{id}.{timestamp}.{body}"` with the base64-decoded secret payload,
  ~5 min timestamp tolerance.
- SMS lifecycle events: `sms.accepted/sent/delivered/undelivered/failed/
  rejected/expired` (event data: `sms_id`, `to`, `from`, `carrier`,
  `error{code, description}`).
- Voice (`/v1/voice/calls`), WhatsApp send/templates and Numbers exist on
  the platform (authenticated probes) but are not yet publicly
  documented; their request/response shapes are asserted and must be
  confirmed against the live API.
- The official `bird-sdk-python` (PyPI `messagebird-sdk`) covers only the
  email product of this platform.

## Decision

### 1. Target the developer platform; raw HTTP, no SDK

All access goes through one helper `connect.settings.bird_request()`:
Bearer auth, base `https://{region}.platform.bird.com/v1` with the region
inferred from the key prefix (`bk_eu1_...` → `eu1`, override via
`ir.config_parameter connect.bird_api_url`). Collections iterate with
cursor pagination (`data` / `next_cursor`) via `bird_paginate()`. The SDK
is not used (email-only surface); no new external Python dependency
(`httpx` already ships with core).

### 2. Scope: messaging + voice ledger + callback click-to-call

- SMS/WhatsApp send/receive including WhatsApp templates
  (`connect.bird.message_template`, synced from
  `/v1/whatsapp/templates`).
- Click-to-call is a **two-leg callback originate** (`POST
  /v1/voice/calls`): Bird first dials the agent's real phone
  (`connect.user.bird_phone_number`), then connects the destination. No
  web phone — Bird has no browser SDK.
- The call ledger is fed from `voice.*` webhook events normalized into
  the core `connect.channel.process_channel_event()` /
  `connect.call.process_call_event()` pipeline. Inbound call routing
  stays on the Bird side; Odoo records the events.

### 3. Provider-owned models (ADR-031)

`connect.bird.number` (sender identity registry synced from
`/v1/numbers` — every send/originate carries a `from` out of it),
`connect.bird.message_template`, `connect.bird.message_configuration`
(deliberate full copy of the Twilio analog, no mixins),
`connect.bird.webhook` (endpoint registry). Ledger models are extended
via `_inherit` adapters only (`bird_message_id`, `bird_call_id`, status
mapping, recording fetch).

### 4. Single webhook endpoint, one registration

One public route `/bird/webhook` dispatches on the envelope `type`.
`setup_bird_webhooks()` registers one endpoint for all products
(`POST /v1/webhooks`) and stores the one-time `whsec_` secret on
`connect.settings`; re-runs are idempotent because the secret cannot be
re-fetched. Unknown event names in the requested list fall back to the
published SMS subset so setup cannot hard-fail. Handlers are idempotent
(dedupe by `bird_message_id`, channel upsert by call id) and always
answer 200 after signature validation; signature failures answer 401 so
Bird keeps retrying while the secret is being fixed.

### 5. Message-provider dispatch in core

Twilio was the only messaging provider and overrode
`connect.message.send()` unconditionally; co-installing a second
messaging provider needs the same dispatch the click-to-call path already
has (ADR-031 §5). Core gains `connect.user.message_provider` (Selection,
`selection_add` per provider), `connect.settings._get_message_provider()`
and an abstract `connect.message.send()` terminal raising a clear
UserError. Provider `send()` overrides guard on their key and fall
through to `super()`. Single-provider installs need zero configuration.
*Rejected alternative:* dispatch by ownership of the sender number —
implicit, breaks when both providers hold the same number, and gives no
user-visible control.

### 6. Recordings are downloaded immediately, refreshed for transcription

Recording download links are short-lived pre-signed URLs, so a cron picks
completed calls flagged `bird_recording_pending`, lists recordings per
call (`/v1/voice/calls/{id}/recordings`) and stores the audio as an
attachment right away (`source='bird'`), with an attempt counter because
recordings lag call completion. `get_transcript()` refreshes the URL
before delegating to core for deferred transcription.

## Consequences

- New module `connect_bird` 19.0.1.0.0, `depends: ['connect']`; core
  `connect` and `connect_twilio` get one version bump each for the
  dispatcher change.
- Wire shapes not yet published by Bird (voice call origination and
  events, WhatsApp send/template payloads, numbers listing) are asserted
  from the platform's conventions and isolated in single
  builders/mappers (`_build_bird_originate_payload`, `_map_bird_params`,
  `_extract_bird_message_data`, `_map_remote_number`,
  `_map_remote_template`) — they are the only places touched when live
  verification (pending an access key with sms/voice/whatsapp/webhooks
  scopes) corrects them.
- WhatsApp free-form sends outside the 24-hour window fail server-side;
  `send()` falls back to SMS and the composer offers approved templates.
- `connect.group_user` gets read access on `connect.bird.number` and
  `connect.bird.message_template` (needed by the composers);
  `connect.bird.message_configuration` and `connect.bird.webhook` are
  admin-only (owner decision).
