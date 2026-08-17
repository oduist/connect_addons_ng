# connect_telnyx — agent notes

Module-specific guidance. The repository-wide rules in the root `AGENTS.md`
still apply.

## Debugging a call

A Telnyx call leaves three independent trails: the Odoo ledger, the Odoo debug
log, and Telnyx's own APIs. Work through them in that order — the answer is
usually in the first two, and only a provider-side failure needs the third.

### 1. Odoo ledger and debug log

`connect.call` / `connect.channel` show what Odoo made of the call, and
`connect.debug` holds the raw webhook payloads (the module writes them through
`debug()` with secrets already redacted by
`connect_telnyx/models/utils.py::format_telnyx_debug_payload`).

```python
call = env['connect.call'].search([], order='id desc', limit=1)
print(call.status, call.duration, call.has_error, call.error_code,
      call.error_message, call.telnyx_ai_conversation_id)
for record in env['connect.debug'].search(
        [('create_date', '>=', '2026-08-17 18:28:00')], order='id asc'):
    print(record.id, record.create_date, record.message[:200])
```

A call that is short and unremarkable in the ledger is the usual sign that the
failure happened on the Telnyx side after the call was answered.

### 2. Telnyx APIs

Every request below is a plain REST call with the stored key. Never print the
key itself:

```python
settings = env['connect.settings'].sudo()
settings.telnyx_api_request('GET', '/ai/assistants/<sid>/versions')
```

`telnyx_api_request` expects JSON, so use `requests` with
`Authorization: Bearer <key>` for endpoints that return audio or other binary
data.

**`GET /v2/call_events`** — the full timeline of one call leg: application
events, executed commands and webhook attempts, each with the payload Telnyx
sent. This is the single most useful endpoint. Filter by
`filter[leg_id]`, `filter[application_session_id]`, `filter[name]` or
`filter[occurred_at][gte]`; `failed` marks an event Telnyx itself considers
failed. The leg id arrives in call-progress webhooks as `CallLegId`, the
session as `CallSessionId`.

**`GET /v2/webhook_deliveries`** — what Telnyx tried to deliver to Odoo, with
every attempt, its request headers (including the Ed25519 signature) and the
HTTP response. Use it when Odoo has no trace of an event at all, or when a
controller returned 4xx/5xx.

**`GET /v2/detail_records?filter[record_type]=...`** — usage records. The type
must be one Telnyx accepts, otherwise it answers `10011 Bad Request` and names
the rejected value; `conference`, `messaging`, `webrtc`, `amd`, `verify`,
`wireless`, `media_storage`, `fax` and `inference` work. `inference` carries
AI token usage and cost per conversation.

**`GET /v2/ai/conversations/<id>`** — an AI conversation with its `error`
field, metadata and assistant version; `/messages` lists the turns. An empty
message list with a populated `error` means the assistant never spoke.

**`GET /v2/ai/assistants/<sid>/versions`** — every published assistant
version. When calls that used to work start failing, diff the current version
against the last good one; the field that changed is the cause. Flattening
both versions and comparing key by key is faster than reading the JSON.

### 3. Reproducing a synthesis failure without a call

`POST /v2/text-to-speech/speech` with `{"text": ..., "voice": ...,
"voice_settings": {...}}` answers `400` code `90103` for a voice/settings
combination the provider cannot render. This turns "the agent hangs up
instantly" into a one-second check.

## AI assistant failures

An assistant that answers and hangs up after about a second did not fail as a
call: the leg is reported `completed` with `HangupCause=normal_clearing`. The
real outcome is the separate `CallStatus=conversation_ended` webhook and its
`Reason` — for example `greeting_error`, which means text-to-speech could not
render the greeting.

`connect.call.on_telnyx_call_status` maps such a failure onto the ledger
(`has_error`, `error_code`, `error_message`), so check the **Error** tab of
the call before reaching for the Telnyx APIs. Reasons that are not failures,
such as a caller hanging up, are deliberately not errors, and the reason list
is not documented — unknown failure reasons are reported verbatim.

Voice speed is constrained to `[0.5, 1.5]` because Telnyx rejects speeds the
selected voice does not support (ADR-057); Telnyx Ultra additionally needs at
least 0.8.

## Live testing

Provider behavior that only appears on a real account — outbound voice
profiles, whitelisted destinations, SIP URI calling preference, credential
provisioning — is not reproducible with mocks. Test against a real environment
and a real phone before claiming a fix works.
