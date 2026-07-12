# ADR-038: connect_dograh — FreeSWITCH provider for Dograh voice agents

## Problem

Issue #59 asks to connect our FreeSWITCH stack to
[Dograh](https://github.com/dograh-hq/dograh) — an open-source,
self-hostable Vapi/Retell alternative (drag-and-drop voice-agent
workflow builder on top of Pipecat, BSD-2) — via its custom telephony
provider mechanism. Dograh ships providers for Twilio, Vonage, Plivo,
Cloudonix, Vobiz and Asterisk ARI, but not FreeSWITCH. Unlike
connect_pipecat (where we own the whole AI sidecar), the STT/LLM/TTS
pipeline, workflow logic, run history and transcripts all live in
Dograh; our job is transporting call audio to it and giving it call
control over FreeSWITCH.

Dograh's provider contract (studied at upstream commit `2c803bb`,
2026-07-11, just past `dograh-v1.41.0`):

- A provider is a self-registering Python package inside Dograh's API
  service (`api/services/telephony/providers/<name>/`) with a frozen
  `ProviderSpec` (config schema, transport factory, wire sample rate,
  UI form metadata). Exactly two one-line edits outside the package
  (`providers/__init__.py` import, `schemas/telephony_config.py`
  union). The run `mode` column is VARCHAR — no enum/migration needed.
- Inbound: one org-wide webhook `POST /api/v1/telephony/inbound/run`.
  The dispatcher detects the provider (`can_handle_webhook`), matches
  `telephony_phone_numbers.address_normalized` against the called
  number (short extensions normalize as `sip_extension`, so "9001"
  works), verifies the signature, creates the workflow run, and calls
  the provider's `start_inbound_stream(websocket_url=...)` whose return
  value is the HTTP response. The media WS URL is the **generic** core
  route `wss://…/api/v1/telephony/ws/{workflow_id}/{org_id}/{run_id}`;
  no provider-specific WS route is required.
- The number→workflow mapping (`inbound_workflow_id`) is configured in
  Dograh's Phone Numbers UI, exactly like the ARI provider.
- Matching requires a non-empty `account_id_credential_field`: the
  webhook payload must carry an account id equal to a credential field
  of the Dograh-side provider config.
- Media: `FastAPIWebsocketTransport` + a per-provider `FrameSerializer`
  (Asterisk's: raw binary μ-law 8 kHz frames, JSON text control events,
  transfer/hangup via pluggable strategies executed on
  EndFrame/CancelFrame).
- Outbound: providers implement `initiate_call(to_number, webhook_url,
  workflow_run_id, from_number)`; Dograh's campaign/test-call flows
  call it and the answered leg connects to the same generic media WS.
- External REST auth: `X-API-Key` service keys (Odoo→Dograh);
  transcripts/recordings are per-run artifacts in MinIO.

## Decision

Ship one repo PR with two halves:

1. **`connect_dograh` Odoo module** (depends `connect`,
   `connect_freeswitch`) — thin `connect.dograh.agent` model
   (extension mapping only; prompts/models live in Dograh), a
   `dst` Reference extension on `connect.freeswitch.exten`, a
   `dialplan_dograh_agent` FreeSWITCH template, Dograh settings on
   `connect.settings` (standalone settings form per AGENTS.md), and a
   Bearer-token control plane `/dograh/api/{hangup,originate}` running
   as the webhook user.
2. **A `freeswitch` provider package for Dograh**, vendored under
   `connect_dograh/deploy/`, built into an overlay image
   `oduist/dograh-api` (pinned upstream base + package copy + the two
   registration edits as a patch). Upstreaming to dograh-hq/dograh is a
   follow-up so Dograh Cloud users eventually get it natively.

### Call flows

Inbound: FreeSWITCH requests the per-call dialplan from Odoo
(mod_xml_curl). For a Dograh extension the Odoo handler synchronously
POSTs Dograh's `/inbound/run` (payload marked `provider=freeswitch`,
carrying `account_id`, caller/called numbers and the FS `uuid` as
`call_id`; authenticated by the shared `dograh_service_token`). Our
provider's `start_inbound_stream` returns
`{"websocket_url": …, "workflow_run_id": …}`; Odoo renders a dialplan
that answers, exports the run id into channel vars, attaches
`uuid_audio_fork` (bidirectional raw L16 @ 16 kHz, `{"type":
"killAudio"}` barge-in — mechanics proven by connect_pipecat/ADR-035)
to that URL, optionally starts `record_session` via the existing
recording webhook, and parks. The webhook round-trip during dialplan
rendering matches the Twilio-style latency budget (~one HTTP call).

Media: the provider's `FreeswitchFrameSerializer` (defined in the
provider package, modelled on pipecat's `AsteriskFrameSerializer` and
connect_pipecat's `AudioForkFrameSerializer`) translates binary L16
16 kHz frames both ways, emits `killAudio` on interruption, and on
EndFrame/CancelFrame executes a hangup strategy that calls back into
Odoo (`/dograh/api/hangup` → `uuid_kill`), since only Odoo holds
FreeSWITCH XML-RPC credentials.

Transfers: **not supported in v1** (`supports_transfers()` returns
False, like the shipped Cloudonix provider). Dograh's transfer engine
is conference/second-leg shaped — `provider.transfer_call` must
originate a destination leg, report its progress through Redis
pub/sub events, and swap media on EndFrame — which for FreeSWITCH
requires Odoo-mediated leg originate + status reporting + `uuid_bridge`
on both sides. Deferred to a follow-up; the workflow engine already
degrades gracefully ("provider does not support transfer").

Outbound (M2): the provider's `initiate_call` POSTs Odoo
`/dograh/api/originate`; Odoo originates through the existing outgoing
route/caller-ID machinery and connects the answered leg to the same
media WS. Originate outcome is reported to the provider's
status-callback route so campaign dispositions work.

Ledger: FreeSWITCH CDRs already create `connect.call`/`connect.channel`
records. Transcript/summary sync from Dograh run artifacts into
`connect.recording` is best-effort (Odoo pulls via `X-API-Key` after
the CDR lands); if the artifact API proves unstable, core OpenAI
transcription of the local recording already covers the need.

### Auth model

One generated shared secret `dograh_service_token` authenticates both
directions of the control plane: Odoo→Dograh inbound webhooks
(`verify_inbound_signature` compares it, fails closed) and
Dograh→Odoo `/dograh/api/*` (Bearer, `secrets.compare_digest`,
webhook-user env after auth, `readonly=False` routes). FreeSWITCH→
Dograh media WS carries identity only in the URL path (workflow/org/
run ids are unguessable only jointly — same exposure as every other
Dograh provider, TLS assumed). Odoo→Dograh REST uses a Dograh service
key (`X-API-Key`). A `dograh_account_id` settings field must equal the
`account_id` credential of the Dograh-side config — this is what lets
`/inbound/run` match the right org/config and supports multiple Odoo
instances per Dograh org.

## Options considered

- **Emulate an existing Dograh provider** (pretend to be Twilio media
  streams via a translating shim): no Dograh fork needed, but fragile
  (TwiML answers, HMAC signatures, base64 μ-law hop) and an extra
  service to operate. Rejected.
- **ARI-style control plane (Dograh connects to FreeSWITCH ESL)**:
  symmetric with the Asterisk provider but exposes ESL to the Dograh
  host and duplicates call-control logic Odoo already owns via
  XML-RPC. Rejected.
- **mod_audio_stream / WAV-over-ESL** instead of mod_audio_fork:
  already rejected in ADR-035 (no reliable return path / latency).
- **Wait for upstream FreeSWITCH support**: issue open since 2026-05
  with no movement; we control neither timeline nor design. Rejected,
  but upstreaming our provider is the planned follow-up.

## Consequences

- FreeSWITCH images must include the vendored mod_audio_fork
  (introduced by the connect_pipecat branch; runtime uses the published
  `oduist/freeswitch:2.1.0`+ images). If connect_pipecat merges first
  we rebase; otherwise the `connect_freeswitch/deploy/` vendoring
  commits are cherry-picked into this branch — the module sources must
  live in the branch that ships images depending on them.
- The overlay image pins one upstream Dograh commit; Dograh's provider
  API is young and moves fast (v1.41.0→HEAD touched 16 telephony files
  in a week), so every overlay rebuild revalidates the patch. The
  registration patch failing to apply is a loud build-time error, not a
  runtime surprise.
- Numbers must be configured twice (FS extension in Odoo, phone number
  + workflow assignment in Dograh) — same operational shape as the ARI
  provider; documented in the admin guide.
- Transfer-to-human from a Dograh workflow is unavailable on FreeSWITCH
  until the follow-up lands; callflows can still route to an agent
  extension before/after the AI leg.
- `connect.dograh.agent` access: admin CRUD, user read, webhook read.
