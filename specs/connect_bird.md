# Connect Bird Module Specification

## Module Info

- **Name:** Oduist Connect Bird
- **Technical:** `connect_bird`
- **Version:** 18.0.1.0.0
- **Depends:** `connect`
- **Python deps:** none (raw HTTP via `httpx`, already required by core)
- **Application:** False
- **License:** Other proprietary

## Overview

The `connect_bird` module integrates Bird.com (formerly MessageBird) with the
core `connect` module (ADR-038). Scope: SMS and WhatsApp messaging (including
WhatsApp message templates), a voice-call ledger fed by Bird voice events,
and click-to-call via a **two-leg callback originate** (Bird dials the agent's
phone first, then connects the destination). Bird has no public WebRTC SDK,
so there is no web phone.

All API access is raw HTTP against the **Bird developer platform**
(`https://{region}.platform.bird.com/v1`, `Authorization: Bearer bk_...`;
the region is inferred from the access key prefix, the workspace is
implicit in the key) — the official `bird-sdk-python` covers only Bird's
email product and is **not** used. The single HTTP entry point is
`connect.settings.bird_request()`; collections iterate via
`bird_paginate()` (cursor pagination, `data`/`next_cursor`).

The shared ledger models (`connect.call`, `connect.channel`,
`connect.message`, `connect.recording`, `connect.user`, `connect.settings`)
are extended via `_inherit`; provider-owned configuration lives in
independent `connect.bird.*` models (ADR-031).

Messaging dispatch: core `connect.message.send()` is a dispatcher terminal;
this module handles the message when
`connect.settings._get_message_provider()` returns `'bird'` and falls
through to `super()` otherwise (mirrors the click-to-call
`originate_provider` machinery).

> Voice call origination/events, WhatsApp send/template payloads and the
> numbers listing exist on the platform but are not yet publicly
> documented; their wire shapes are asserted and isolated in single
> builders/mappers pending live verification (ADR-038).

---

## Models

### Provider-owned models (`connect.bird.*`)

#### `connect.bird.number` — models/bird_number.py

Read-only registry of Bird sender identities: every message send and call
originate carries a `from` out of this registry. Synced from
`GET /v1/numbers`; vanished numbers are deleted with a sticky
notification. Mapping isolated in `_map_remote_number()`.

| Field | Type | Notes |
|-------|------|-------|
| `sid` | Char | Bird number id, indexed |
| `number` | Char | E.164, alphanumeric sender ID or short code; required, indexed |
| `name` | Char | |
| `status` | Char | |
| `capabilities` | Char | comma-separated: sms, whatsapp, voice, mms |
| `is_default` | Boolean | default sender |

Methods: `sync()`, `get_default_number(capability=None)` (default → first
active with the capability → `ValidationError`), `has_capability()`
(permissive when capabilities are unknown).

#### `connect.bird.message_template` — models/message_template.py

Approved WhatsApp templates synced read-only from
`GET /v1/whatsapp/templates` (tolerates a missing whatsapp scope).
Required to start a conversation outside the 24-hour customer-service
window. Fields: `sid`, `name`, `locale`, `status`, `category`,
`variables` (JSON list), `body_preview`. Methods: `sync()`,
`get_variable_keys()`, mapping isolated in `_map_remote_template()`.

#### `connect.bird.message_configuration` — models/message_configuration.py

Routing of inbound messages into Odoo records; deliberate full copy of the
Twilio analog keyed by Bird number (ADR-031: no mixins). Fields: `number`
(M2O `connect.bird.number`), `destination` (Selection, `res.partner`),
`default_values` (Text, python dict literal + constraint).

#### `connect.bird.webhook` — models/bird_webhook.py

Registry of the webhook endpoint registered by `setup_bird_webhooks()`;
makes re-runs idempotent (the signing secret is returned by Bird exactly
once). Admin-only diagnostics. Fields: `sid`, `url`, `status`, `events`.

### Ledger adapters (`_inherit`)

#### `connect.settings` — models/settings.py

| Field | Type | Notes |
|-------|------|-------|
| `bird_access_key` | Char | `groups="base.group_erp_manager"`, masked via `display_bird_access_key` |
| `bird_webhook_signing_key` | Char | the `whsec_` secret issued once by Bird; protected + display mirror |
| `bird_verify_requests` | Boolean | default True (dev page) |
| `bird_signature_tolerance` | Integer | default 300 s (dev page) |
| `bird_sms_category` | Char | default `transactional`; sent with outgoing SMS |
| `bird_ring_timeout` | Integer | default 30 s, agent leg ring timeout |

Methods:

| Method | Description |
|--------|-------------|
| `_get_bird_base_url()` | `https://{region}.platform.bird.com`, region from the `bk_{region}_` key prefix; override via `ir.config_parameter` `connect.bird_api_url` |
| `bird_request(method, path, payload, params, timeout, raise_exc)` | Single HTTP helper: Bearer auth, `/v1` prefix, `connect.debug` logging, normalizes `{code,message}` / `{errors:[...]}` into `ValidationError` (or `False` with `raise_exc=False`) |
| `bird_paginate(path, params)` | Cursor pagination iterator (`data` / `next_cursor` / `starting_after`) |
| `sync_bird()` | Syncs `connect.bird.number` + `connect.bird.message_template` |
| `setup_bird_webhooks()` | Registers ONE endpoint (`POST /v1/webhooks {url, events}`) for `<api_url>/bird/webhook` and stores the one-time `whsec_` secret; unknown event names fall back to the published SMS subset (`_register_webhook_endpoint()`) |
| `_build_bird_originate_payload(agent, from, destination, record, url)` | Isolated payload builder for the two-leg originate (`POST /v1/voice/calls`) |
| `originate_call()` | Dispatcher override: handles the call when `_get_originate_provider(user) == 'bird'`; POSTs the callback originate, then pre-creates the agent leg (`technical_direction='outbound-api'`, `called=<destination>`) so voice events update it |
| `write()` | Protected-field masking for `BIRD_PROTECTED_FIELDS` |

#### `connect.message` — models/message.py

Fields: `bird_message_id` (Char, indexed), `bird_number` (M2O).

| Method | Description |
|--------|-------------|
| `send()` | Dispatch guard (`_get_message_provider() != 'bird'` → `super()`), then `send_bird()` |
| `send_bird()` | Free-form SMS: `POST /v1/sms/messages {to, text, category [, from]}` — `from` is optional (the platform assigns a shared sender when omitted; the ledger stores the actual sender and rendered text from the response). API errors (e.g. the free-form-SMS GA gate) surface verbatim. Sender resolution: `outgoing_callerid` → user's `bird_message_number` → default number → none |
| `send_bird_template(recipient, template, params, ...)` | Template send (the primary path — the platform is template-first): SMS `{to, template: {id|name, parameters: {key: value}}}`; WhatsApp `{to, template: {name, components: [{type: body, parameters: [{type: text, text}]}]}}` (positional params ordered by key). Live-verified payloads |
| `receive_bird(data, event_type)` | Inbound event: dedupe by `bird_message_id`, extraction via `_extract_bird_message_data()` (sms_id/wam ids, plain from/to or WhatsApp contact/business objects, text/media), partner match, conversation threading, `connect.bird.message_configuration` routing, chatter post |
| `update_bird_status(data, event_type)` | Lifecycle events — the status is the event-name suffix (`sms.delivered` → delivered, `undelivered/failed/rejected/expired` → failed with `data.error`/`last_error`); unknown ids upserted |
| `_cron_poll_bird_status(limit=50)` | Cron (5 min): polls `GET /v1/sms|whatsapp/messages/{id}` for recent non-terminal outgoing messages and applies status + `last_error` (`_apply_bird_message_object()`). Needed because the platform delivers webhook events for the email product only so far |
| `_compute_direction()` | Also checks Bird sender numbers |
| `action_retry()` | Re-send failed messages through the dispatcher |

#### `connect.user` — models/user.py

| Field | Type | Notes |
|-------|------|-------|
| `originate_provider` / `message_provider` | Selection | `selection_add=[('bird', 'Bird')]` |
| `bird_phone_number` | Char | agent phone for two-leg click-to-call; in `_pbx_number_fields()` |
| `bird_voice_number` | M2O | caller ID for originate |
| `bird_message_number` | M2O | default sender |

Method: `get_user_by_bird_number(number)` — agent matching in voice events.

#### `connect.channel` — models/channel.py

`on_bird_call_event(data, event_type)` → `_map_bird_params()` →
`process_channel_event()`. Status normalization via `BIRD_CALL_STATUS_MAP`;
the pre-created originate leg keeps `technical_direction='outbound-api'`;
agent legs matched via `bird_phone_number`.

#### `connect.call` — models/call.py

Fields: `bird_call_id`, `bird_recording_pending`,
`bird_recording_attempts`. `on_bird_call_event()` runs the shared pipeline
with error data from failed calls, then flags ended calls for the
recording cron.

#### `connect.recording` — models/recording.py

`fetch_bird_call_recordings(call)` (`GET /v1/voice/calls/{id}/recordings`
→ immediate download to attachment, `source='bird'`), `get_transcript()`
override (refreshes the pre-signed URL first),
`_cron_fetch_bird_recordings()` (2-min cron, 10-attempt cap).

---

## Controllers — controllers/bird_webhooks.py

Single route:

```
POST /bird/webhook   (type='http', auth='public', csrf=False, readonly=False)
```

- **Standard Webhooks** signature verification: headers `webhook-id` /
  `webhook-timestamp` / `webhook-signature` (`v1,<base64>`), HMAC-SHA256
  over `"{id}.{timestamp}.{raw body}"`, key = base64-decoded payload of
  the `whsec_` secret; configurable timestamp tolerance;
  `bird_verify_requests` toggle. Failures → 401 (Bird keeps retrying).
- Envelope `{type, timestamp, data}`; dispatch on `type` under
  `connect.user_connect_webhook`: `sms|whatsapp.received` →
  `receive_bird()`, other `sms|whatsapp.*` → `update_bird_status()`,
  `voice.*` → `connect.call.on_bird_call_event()`.
- Processing errors are logged and answered 200 (poison-pill protection);
  handlers are idempotent.

---

## Wizards

- `sms.composer` inherit (wizard/sms_composer.py): `outgoing_callerid`
  selection unions other providers' numbers (chained `_list_all_numbers`)
  with Bird numbers; `_action_send_sms()` routes through the dispatching
  `connect.message.send()`.
- `connect.bird.whatsapp_composer` (wizard/whatsapp_composer.py): sender
  number + template picker (variables JSON prefilled), free text inside
  the 24-hour window. Calls `send_bird()` / `send_bird_template()`
  **directly** — the composer itself is the explicit provider choice.
  Bound to the res.partner form Action menu.

---

## Security

| Model | admin | user | webhook |
|-------|-------|------|---------|
| `connect.bird.number` | CRUD | read | read |
| `connect.bird.message_template` | CRUD | read | — |
| `connect.bird.message_configuration` | CRUD | — | — |
| `connect.bird.webhook` | CRUD | — | — |
| `connect.bird.whatsapp_composer` | CRUD | CRUD | — |
| `sms.composer` | — | CRUD (own row) | — |

Webhook handlers run as `connect.user_connect_webhook` and use `sudo()`
internally for config lookups; `bird_access_key` /
`bird_webhook_signing_key` are `base.group_erp_manager`-restricted and never
granted to the webhook group.

---

## Views / Menus

```
Connect > Bird                        (menu, seq 50)
  ├─ Numbers                          (connect.bird.number list/form)
  ├─ Messages > Messages              (core connect.action_connect_message)
  └─ Configuration (admin)
      ├─ Settings                     (standalone connect.settings form via
      │                                open_settings_form(), pages: Bird API /
      │                                Development)
      ├─ Message Templates
      ├─ Message Configuration
      └─ Webhook Endpoints
```

Inherited views: core user form (+Bird fields), message form
(+`bird_message_id`/`bird_number`), call form (+`bird_call_id`, dev only),
SMS composer (+`outgoing_callerid`).

Data: `data/ir_cron.xml` — "Connect Bird: Fetch Call Recordings" every 2
minutes.

---

## Tests

`tests_suite/connect_bird/tests/` (private submodule, conditional loader in
`connect_bird/tests/__init__.py`): settings/API helper, webhook endpoint
registration (one-time secret, fallback event list), Standard-Webhooks
signature verification (HttpCase), inbound messages (idempotency, media,
routing, threading), outbound send (payload, WhatsApp→SMS fallback,
dispatch fall-through, templates), lifecycle status events (upsert), voice
event chains, originate (payload, ledger pre-create), recordings (cron,
retries, URL refresh). All HTTP is mocked.
