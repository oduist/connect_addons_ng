# 035 — Bird.com provider module (`connect_bird`)

## Status

Accepted

## Context

Bird.com (formerly MessageBird) is an omnichannel CPaaS: SMS, WhatsApp and
voice served by one HTTP API family under `https://api.bird.com` with
`Authorization: AccessKey <key>` auth, everything scoped to
`/workspaces/{workspaceId}/...`. We add it as the fourth provider on top of
the technology-agnostic `connect` core (ADR-031), next to `connect_twilio`,
`connect_freeswitch` and `connect_asterisk`.

Provider-relevant Bird surface:

- **Channels API** — the config anchor is a *channel* (uuid, platform
  `sms`/`whatsapp`/`voice`, identifier = E.164 number). Sending SMS and
  WhatsApp uses the same endpoint
  (`POST /channels/{channelId}/messages`); WhatsApp outside the 24-hour
  customer-service window only accepts *template* messages (Touchpoints
  API projects, `template: {projectId, version, locale, parameters}`).
- **Voice Calls API** — `POST /channels/{channelId}/calls` with a
  server-side `callFlow` command list (say/playback/gather/bridge/record/
  hangup). There is **no public WebRTC SDK**, so no web phone is possible.
- **Notifications API** — workspace-level webhook subscriptions
  (`sms|whatsapp|voice` × `inbound|outbound`, envelope
  `{service, event, payload}`), signed with HMAC-SHA256 over
  `"{timestamp}\n{url}\n{sha256(body)}"` (headers `messagebird-signature`,
  `messagebird-request-timestamp`), retried for up to 8 hours until 2xx.
- **Recordings API** — recording metadata with a pre-signed S3 `url`
  valid for 600 seconds.

The official `bird-sdk-python` (PyPI `messagebird-sdk` 0.2.2) covers only
Bird's *email* platform plus a different (Standard-Webhooks) verification
scheme; it does not expose Channels/Voice/Notifications APIs.

## Decision

### 1. Raw HTTP via httpx, no SDK dependency

The SDK is useless for this scope, so `connect_bird` talks to the API with
`httpx` directly (already imported by core `connect`), through a single
helper `connect.settings.bird_request()`. No new external Python
dependency; errors are normalized from Bird's `{"errors": [...]}` payloads.

### 2. Scope: messaging + voice ledger + callback click-to-call

- SMS/WhatsApp send/receive including WhatsApp message templates (synced
  from the Touchpoints API into `connect.bird.message_template`).
- Click-to-call is a **two-leg callback originate**: Bird first dials the
  agent's real phone (`connect.user.bird_phone_number`), then the
  `callFlow` `bridge` command connects the destination. No web phone —
  Bird has no browser SDK (unlike Twilio Voice JS / Verto / JsSIP).
- The call ledger is fed exclusively from `voice.inbound`/`voice.outbound`
  webhook events normalized into the core
  `connect.channel.process_channel_event()` /
  `connect.call.process_call_event()` pipeline. Inbound call *routing*
  stays in Bird's own Flow Builder — like connect_asterisk leaves inbound
  routing in the customer dialplan, Odoo only records the events.

### 3. Provider-owned models (ADR-031)

`connect.bird.channel` (synced channel registry — every send/call needs a
channelId), `connect.bird.message_template`,
`connect.bird.message_configuration` (deliberate full copy of the Twilio
analog, no mixins), `connect.bird.webhook` (subscription registry).
Ledger models are extended via `_inherit` adapters only
(`bird_message_id`, `bird_call_id`, status mapping, recording fetch).

### 4. Single webhook endpoint, workspace-wide subscriptions

One public route `/bird/webhook` dispatches on the envelope `event` key —
Bird's envelope makes per-event routes redundant, and one URL keeps
subscription setup and signature verification trivial. Subscriptions are
created **without** per-channel `eventFilters` (6 subscriptions total), so
newly synced channels need no re-subscription. `setup_bird_webhooks()` on
settings provisions them idempotently and generates the signing key.
Handlers are idempotent (dedupe by `bird_message_id`, channel upsert by
`sid`) and always answer 200 after signature validation to absorb Bird's
8-hour retry storms; signature failures answer 401 so Bird keeps retrying
while the key is being fixed.

### 5. Message-provider dispatch in core

Twilio was the only messaging provider and overrode
`connect.message.send()` unconditionally; co-installing a second messaging
provider needs the same dispatch the click-to-call path already has
(ADR-031 §5). Core gains `connect.user.message_provider` (Selection,
`selection_add` per provider), `connect.settings._get_message_provider()`
and an abstract `connect.message.send()` terminal raising a clear
UserError. Provider `send()` overrides guard on their key and fall through
to `super()`. Single-provider installs need zero configuration (single
option auto-selected). *Rejected alternative:* dispatch by ownership of
the sender number — implicit, breaks when both providers hold the same
number, and gives no user-visible control.

### 6. Recordings are downloaded immediately, refreshed for transcription

The pre-signed recording URL dies after 600 s, so a cron picks completed
calls flagged `bird_recording_pending`, lists recordings per call and
stores the audio as an attachment right away (`source='bird'`), with an
attempt counter because recordings lag call completion.
`get_transcript()` refreshes the pre-signed `media_url` before delegating
to core for deferred transcription.

## Consequences

- New module `connect_bird` 19.0.1.0.0, `depends: ['connect']`; core
  `connect` and `connect_twilio` get one version bump each for the
  dispatcher change.
- Exact wire shapes asserted from docs but not yet from live traffic
  (bridge command options, voice payload keys, inbound sender nesting,
  call-recordings list path) are isolated in single builders/mappers
  (`_build_originate_payload`, `_map_bird_params`, `receive_bird`) and
  verified against a live workspace before release.
- WhatsApp free-form sends outside the 24-hour window fail server-side;
  `send()` falls back to the SMS channel and the composer offers approved
  templates instead.
- `connect.group_user` gets read access on `connect.bird.channel` and
  `connect.bird.message_template` (needed by the composers);
  `connect.bird.message_configuration` and `connect.bird.webhook` are
  admin-only (owner decision).
