# connect_dograh — Dograh AI voice agents for FreeSWITCH

Design decision record: `specs/decisions/037-connect-dograh-freeswitch-provider.md`.

Two-part integration (ADR-037):

1. This Odoo module (depends `connect`, `connect_freeswitch`) — config,
   dialplan routing, Dograh→Odoo control plane.
2. A vendored **freeswitch telephony provider package for Dograh**
   under `connect_dograh/deploy/`, shipped as the overlay image
   `oduist/dograh-api:<dograh-ver>-<module-ver>` (base image pinned;
   `register_freeswitch_provider.py` applies the two upstream
   registration edits and fails the build on drift).

## Models

### connect.dograh.agent (new)

| Field | Type | Notes |
|-------|------|-------|
| name | Char, required | |
| active | Boolean, default True | archive ribbon |
| workflow_id | Char | informational; mapping lives in Dograh Phone Numbers |
| exten | M2o connect.freeswitch.exten, readonly | back-link via exten `dst` Reference |
| exten_number | Char related exten.number, stored | |
| record_calls | Boolean, default True | standard recording webhook |
| notes | Text | |

Methods:

- `create_extension()` — delegates to
  `connect.freeswitch.exten.create_extension(self, 'connect.dograh.agent')`.
- `_dograh_start_inbound_run(params, number)` — POST
  `{api_url}/api/v1/telephony/inbound/run` (Bearer
  `dograh_service_token`, timeout 5 s) with
  `{provider: freeswitch, account_id, call_id: Caller-Unique-ID,
  from_number, to_number, direction: inbound}`. Returns the reply dict
  (`websocket_url`, `workflow_run_id`) or None on any failure.
- `generate_dialplan(params, exten=None)` — dst-Reference dispatch
  target. Success: renders `dialplan_dograh_agent` (answer →
  `uuid_audio_fork <ws_url> mono 16k dograh {} true true 16000` →
  optional `record_session` → park). Failure: 486 dialplan.

### connect.freeswitch.exten (inherit)

`dst = fields.Reference(selection_add=[('connect.dograh.agent', 'Dograh AI Agent')])`

### connect.settings (inherit)

| Field | Notes |
|-------|-------|
| dograh_api_url | Char; normalized via `get_dograh_api_url()` |
| dograh_account_id | Char, default `odoo`; must match provider config in Dograh |
| dograh_service_token | Char, admin-only, default `token_urlsafe(32)`; display twin `display_dograh_service_token` in PROTECTED_FIELDS; strength-validated on write |
| dograh_status | Char readonly; `check_dograh_status()` GETs `{api_url}/api/v1/health` |

- `dograh_originate(to_number, websocket_url, from_number=None,
  run_id=None)` — validates inputs against originate-dialstring
  metacharacters (ADR-026), resolves the outgoing route
  (`connect.freeswitch.outgoing_route`), falls back to the default
  `outgoing_callerid`, and runs
  `originate {origination_uuid,...,dograh_ws_url=...}<gateway-leg>
  dograh_outbound XML default`. Returns `(dict, http_status|None)`.

## Controllers

All Dograh→Odoo routes: `type='http'`, `auth='public'`, `csrf=False`,
`readonly=False`, Bearer `dograh_service_token`
(`secrets.compare_digest`, fail-closed), executed as
`connect.user_connect_webhook`.

| Route | Purpose |
|-------|---------|
| POST /dograh/api/hangup | `uuid_kill <call_uuid>`; 404 when the channel is already gone, 502 when FS is unreachable |
| POST /dograh/api/originate | outbound leg for Dograh campaigns/test calls (see `dograh_originate`) |

`DograhFreeSwitchXMLController` extends the connect_freeswitch
mod_xml_curl controller: `_route_internal('dograh_outbound')` serves
the `dialplan_dograh_outbound` template (audio_fork to the
`${dograh_ws_url}` channel variable + park); everything else falls
through to super.

## FreeSWITCH templates (data/fs_templates.xml)

- `dialplan_dograh_agent` — inbound agent extension.
- `dialplan_dograh_outbound` — landing extension for Dograh-originated
  outbound legs.

## Dograh provider package (deploy/providers/freeswitch/)

`ProviderSpec(name="freeswitch", transport_sample_rate=16000,
account_id_credential_field="account_id")`. Config credentials:
`account_id`, `odoo_url`, `service_token` (sensitive), `from_numbers`.

- `provider.py` — `can_handle_webhook` (`provider == "freeswitch"`),
  `parse_inbound_webhook`, `verify_inbound_signature` (Bearer ==
  service_token, fail closed), `start_inbound_stream` → JSON
  `{websocket_url, workflow_run_id}` back to Odoo, `handle_websocket` →
  `run_pipeline_telephony` (version-adaptive: `organization_id` on
  current Dograh, `user_id` on <= 1.41.0), `initiate_call` → builds the
  media WS URL and POSTs Odoo `/dograh/api/originate`,
  `supports_transfers()` → False (v1).
- `serializers.py` — `FreeswitchFrameSerializer`: binary L16 both ways
  (stream-resampled), `{"type": "killAudio"}` on interruption, hangup
  strategy on EndFrame/CancelFrame.
- `strategies.py` — `OdooHangupStrategy` → POST `/dograh/api/hangup`.
- `transport.py` — `FastAPIWebsocketTransport` factory
  (`load_credentials_for_transport`, `call_uuid` transport kwarg).

## Security

- `connect.dograh.agent`: `connect.group_admin` CRUD,
  `connect.group_user` read-only, no webhook-group access (dialplan and
  control plane run via sudo/settings).
- Settings fields admin-only; service token masked via display twin.

## Views / Menu

**Dograh** submenu under the Connect app (sequence 50): AI Agents
(list/form with Create Extension button), Configuration → Settings
(standalone `connect.settings` form via `open_settings_form`, per
AGENTS.md — no notebook-page injection).

## Tests (connect_dograh/tests/)

`test_agent` (exten linking, dialplan render against mocked inbound
webhook, recording toggle, failure paths), `test_settings` (URL
normalization, health check, token validation), `test_controllers`
(hangup auth/dispatch), `test_originate` (route matching, caller-ID
fallback, input validation, HTTP endpoint, dialplan hook).

## Limitations (v1)

- No transfer-to-human from Dograh workflows on FreeSWITCH.
- Dograh-side transcripts are not synced into the ledger; recordings
  made via `record_calls` use the core OpenAI transcription instead.
- Outbound originate is synchronous (blocks up to ~25 s until answer);
  no ringing/AMD status callbacks yet.
