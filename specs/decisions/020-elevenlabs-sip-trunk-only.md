# ADR-020: ElevenLabs Transport — SIP Trunk Only

**Status:** Accepted
**Date:** 2026-05-17
**Supersedes:** ADR-015, ADR-017, ADR-019
**Relates:** ADR-014, ADR-016, ADR-018

## Context

Four ADRs over the last sprint accumulated a two-transport-per-provider
matrix for `connect_elevenlabs`:

| Provider | Transport A | Transport B |
|---|---|---|
| Twilio (ADR-017) | `media_stream` (WSS to relay) | `sip_trunk` (`<Dial><Sip>`) |
| FreeSWITCH (ADR-015/016) | `audio_fork` (WSS to relay) | `sip_trunk` (`sofia/gateway`) |

Plus ADR-019 placed a per-agent SIP-trunk configuration block on
`connect.elevenlabs_agent` in preparation for per-number provisioning
that has not been built.

Operating cost of this matrix in practice:

* `connect_elevenlabs/service/` (FastAPI relay + `TwilioAudioInterface`)
  is a separate deployable container with its own Docker image,
  ngrok/public-URL requirement, Odoo JSON-RPC login, and a parallel
  audio path. It exists solely for the two WebSocket transports.
* `connect.elevenlabs_agent` carries a transport selector for each
  provider (`twilio_transport`, `fs_transport`), and a SIP-trunk config
  block (`sip_enabled`, `sip_username`, `sip_password`,
  `sip_inbound_addresses`, `sip_outbound_addresses`,
  `sip_allowed_numbers`, `sip_override_credentials`) whose
  `_resolve_sip_credentials()` helper has zero callers in the current
  codebase. ADR-019 explicitly marked per-number provisioning out of
  scope.
* Both bridges duplicate ~30 lines of extension-resolution logic in
  `transfer()` that differ only by the final REST/ESL call.

Personalization (partner name, language, greeting, published-extension
list) was injected into the EL Conversation as `dynamic_variables` by
the relay's `start_call_event` JSON-RPC into Odoo. Agents already on
`sip_trunk` today silently lose this personalization — there is no
equivalent hook in the SIP-trunk paths.

ElevenLabs now offers a first-class **Conversation Initiation Webhook**
(`workspace.conversation_initiation_client_data_webhook` / per-agent
override). EL POSTs to a URL we provide when a conversation starts and
expects a JSON body with `dynamic_variables` and
`conversation_config_override`. That is functionally the replacement
for the relay's `start_call_event` round-trip — but without the relay,
without the WebSocket, and without an extra deployable.

## Decision

Adopt a single transport — **SIP Trunk** — for both Twilio and
FreeSWITCH. Delete the relay and the WebSocket-based transports.
Replace the relay's `start_call_event` personalization hook with an
Odoo controller that implements EL's Conversation Initiation Webhook.

### Demolition

Removed entirely:

* `connect_elevenlabs/service/main.py` (FastAPI app, `/twilio/stream/...`,
  `/agent/ping`).
* `connect_elevenlabs/service/twilio_audio_interface.py`.
* `connect.settings.elevenlabs_agent_url` + the `ping_agent` button +
  the corresponding settings-view block.
* `connect.call.elevenlabs_agent_start_call_event()` +
  `elevenlabs_agent_get_call_data()` (the JSON-RPC entry the relay
  called; its logic is ported into the new webhook handler).
* From `connect.elevenlabs_agent`: `sip_enabled`,
  `sip_inbound_addresses`, `sip_outbound_addresses`,
  `sip_allowed_numbers`, `sip_override_credentials`, `sip_username`,
  `sip_password`, and `_resolve_sip_credentials()`. Tenant-level
  `connect.settings.elevenlabs_sip_*` (consumed by
  `elevenlabs_sync_sip_trunks`) is preserved.
* From `connect_elevenlabs_twilio.agent`: `twilio_transport` field and
  the `media_stream` branch in `render()`. `twilio_sip_host` stays.
* From `connect_elevenlabs_freeswitch.agent`: `fs_transport` field and
  `_check_fs_transport_audio_format` constraint. The
  `dialplan_elevenlabs_audio_stream` template (and any view block whose
  only purpose was choosing the transport) is removed.

### Unified bridge contract

`connect.elevenlabs_agent` (core) exposes three explicit extension
points as `NotImplemented`-style stubs:

```python
def render(self, request, params=None):
    """Twilio bridge entry — returns TwiML. Overridden in
    connect_elevenlabs_twilio."""

def generate_dialplan(self, params, exten=None):
    """FreeSWITCH bridge entry — returns dialplan XML. Overridden in
    connect_elevenlabs_freeswitch."""

@api.model
def transfer(self, channel_sid=None, exten=None):
    """Transfer-tool callback — overridden by each bridge to drive the
    provider-specific REST/ESL call."""
```

A new core helper deduplicates extension lookup:

```python
def _resolve_transfer_target(self, exten_str):
    """Returns (exten_rec, None) on success or (None, err) on failure.
    Encapsulates: empty/non-alnum validation, exact match,
    single-published fallback, multi-published "available extensions"
    listing, no-published error."""
```

Both bridges call it before invoking the provider-specific transfer
operation. The duplicated ~30-line block in `_twilio.agent.transfer`
and `_freeswitch.agent.transfer` collapses to two lines.

Twilio bridge `render()` becomes a single TwiML shape:
`<Response><Dial><Sip>sip:<agent_uid>@<twilio_sip_host>?X-Call-Sid=<CallSid></Sip></Dial></Response>`.

FreeSWITCH bridge `generate_dialplan()` always renders the
`dialplan_elevenlabs_sip` template (the only one left).

### Conversation Initiation Webhook

New controller in `connect_elevenlabs/controllers/main.py`:

```python
@http.route('/connect_elevenlabs/conversation_init',
            methods=['POST'], type='http', auth='public', csrf=False)
def conversation_init_webhook(self):
    """EL Conversation Initiation Webhook.

    EL POSTs at conversation start with caller_id (E.164), called_id,
    agent_id, conversation_id. We resolve partner from caller_id,
    pick language, list published extensions, and return the JSON body
    EL expects (dynamic_variables + conversation_config_override).

    Auth: HMAC by elevenlabs_post_call_webhook_secret (same pattern
    as /connect_elevenlabs/post_call)."""
```

Agent-side helper that builds the response (pure server logic, ported
from the relay's `elevenlabs_agent_get_call_data`):

```python
def _build_conversation_init_response(self, caller_id, called_id):
    """Return the conversation-initiation dict EL expects.
    Resolves partner, language, greeting, published extensions."""
```

`update_elevenlabs_agent()` is extended to push the webhook URL into
the agent's platform settings on every sync, so the per-agent override
stays in lockstep with Odoo's controller route.

## Consequences

* `connect_elevenlabs` becomes a single Odoo deployable. No FastAPI
  container, no public-URL requirement beyond Odoo itself, no
  parallel audio path. Recording, transcription and post-call
  summarization continue to work — they are handled by EL itself and
  delivered via the existing `/connect_elevenlabs/post_call` webhook.
* Personalization is preserved (option 1 of the brainstorm) via the
  Conversation Initiation Webhook; SIP-trunk agents now have the same
  dynamic-variable injection that the relay path used to provide.
* Per-agent SIP-trunk provisioning (ADR-019's motivation) is deferred
  to a future ADR that will re-introduce the necessary fields when
  the `POST /v1/convai/phone-numbers` flow is actually built.
* Twilio Media Streams users and FS `audio_fork` users (none in
  production) have no migration path within this ADR; both transports
  are removed cleanly. If a future requirement demands relay-side
  audio (real-time analytics, prompt injection, custom audio mux), a
  separate ADR will restore the relay as an opt-in deployable.

## Migration

None. The affected fields (ADR-019 per-agent SIP block,
`twilio_transport`, `fs_transport`) were added within this dev branch
and have no production data. Orphaned columns left in the DB after the
model fields are removed are harmless — Odoo does not enforce them and
they will be dropped naturally when the DB is recreated for the next
deploy. Removed `ir.model.data` records (views, the
`dialplan_elevenlabs_audio_stream` template) are cleaned up by
`-u connect_elevenlabs*` on the standard update cycle.

## Docs

* `docs/admin/elevenlabs-setup.md` — drop relay/agent_url section,
  document SIP-trunk-only setup end-to-end.
* `docs/admin/elevenlabs-twilio.md` — drop media_stream section.
* `docs/admin/elevenlabs-freeswitch.md` — drop audio_fork section.
* New section in admin docs: configuring the Conversation Initiation
  Webhook URL in the EL dashboard (or relying on auto-sync from
  `update_elevenlabs_agent`).

## Out of scope

* Per-number SIP-trunk provisioning via `POST /v1/convai/phone-numbers`
  (will reintroduce the necessary fields with a real consumer).
* Outbound calls originated by ElevenLabs through the trunk.
* Restoring relay-side audio for analytics / prompt injection — would
  be a separate, opt-in deployable in a future ADR.
