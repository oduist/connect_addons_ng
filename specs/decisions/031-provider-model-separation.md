# 031: Provider Model Separation (Twilio / FreeSWITCH / Asterisk)

## Problem

The original architecture placed "shared" PBX configuration models in
the core `connect` module — `connect.exten`, `connect.callflow` (+
`connect.callflow_choice`), `connect.number`, `connect.endpoint`,
`connect.outgoing_callerid`, `connect.user_callflow`,
`connect.message_configuration` — and let each provider module extend
them via `_inherit`. This was a conceptual mistake: a FreeSWITCH
extension has nothing to do with a Twilio extension, caller IDs and
numbers belong to one specific telephony system, SIP domains are a
purely Twilio structure. Each telephony system lives in its own
numbering plan and its own business logic; there is no call path
between extension 100 on FreeSWITCH and extension 200 on Asterisk.

Concrete symptoms:

- One shared table per concept means rows from different providers mix
  with no discriminator.
- `connect_twilio` makes `username` and `domain` **field-level
  required** on `connect.user`, so co-installing `connect_twilio` with
  `connect_freeswitch` is de-facto broken (an FS-only user cannot be
  created).
- `originate_call` is defined on `connect.settings` independently by
  connect_twilio and connect_asterisk without `super()` — last loaded
  wins; on an FS-only install `connect.call.redial` raises
  `AttributeError` because FS defines it on `connect.call` instead.
- The single top-level "Connect" menu mixes truly common features
  (calls, recordings, transcription) with provider-only ones (TwiML,
  SIP domains, gateways, firewall).

## Decisions

All decided by the product owner:

1. **Full model separation.** Provider-specific models move out of
   core into the provider modules as independent models:

   | Old core model | connect_twilio | connect_freeswitch | connect_asterisk |
   |---|---|---|---|
   | connect.exten | connect.twilio.exten | connect.freeswitch.exten | `asterisk_exten_number` Char on connect.user |
   | connect.callflow (+choice) | connect.twilio.callflow (+_choice) | connect.freeswitch.callflow (+_choice) | — |
   | connect.number | connect.twilio.number | connect.freeswitch.number | connect.asterisk.number (DID→user assist) |
   | connect.endpoint | — | connect.freeswitch.endpoint | connect.asterisk.endpoint |
   | connect.outgoing_callerid | connect.twilio.outgoing_callerid | connect.freeswitch.outgoing_callerid | — |
   | connect.user_callflow (+_call) | connect.twilio.user_callflow (+_call) | — | — |
   | connect.message_configuration | connect.twilio.message_configuration | — | — |

   For naming consistency `connect.twiml` → `connect.twilio.twiml` and
   `connect.domain` → `connect.twilio.domain`.

2. **No mixins — full code duplication.** Considered core
   AbstractModel mixins (`connect.exten.mixin` etc.) to share the
   non-trivial common code (exten dst-Reference plumbing, callflow
   language list, E.164/is_default caller-ID logic). Rejected by the
   owner in favor of maximal module independence: each provider owns a
   complete copy. Consequence (accepted): fixes to these duplicated
   areas must always be applied to both connect_twilio and
   connect_freeswitch.

3. **`connect.channel` stays in core.** Unlike extensions/numbers it
   is not provider configuration but a leg of the shared call history
   (`connect.call.channels` O2M, `connect.recording.channel` M2O). All
   three providers write into it through the common
   `process_channel_event()`: Twilio adds only adapter methods,
   Asterisk adds three adapter fields, FreeSWITCH does not inherit it
   at all. Splitting it would split the call history itself.

4. **`connect.user` stays in core** (calls/channels/recordings
   reference it). It is slimmed: loses `exten`, `outgoing_callerid`,
   `endpoint_ids`, `callflow`; gains provider-neutral hooks
   (`_pbx_number_fields()` / `get_pbx_number()`) and per-provider
   fields contributed by provider modules (`twilio_exten`,
   `freeswitch_exten`, `asterisk_exten_number`, per-provider caller-ID
   and endpoint O2Ms). Twilio's `username`/`domain` become
   `required=False` with a conditional constraint (required only when
   SIP/client is enabled), fixing co-installation.

5. **Click-to-call provider is a user choice.** New
   `connect.user.originate_provider` Selection (base empty, each
   provider `selection_add`s its key). Core
   `connect.settings.originate_call()` dispatches: explicit user
   choice → that provider; exactly one provider installed → that one;
   otherwise a clear UserError. Provider overrides chain via
   `super()`.

6. **Menu separation.** Top-level menus per app: **Connect** (Calls →
   {Calls, Recordings, Channels(admin)}, Users, Configuration →
   {Settings, Debug, License}), **Twilio** (numbers, extensions, call
   flows, caller IDs, TwiML, SIP domains, Messages incl. message
   configuration and WhatsApp, Settings), **FreeSWITCH** (numbers,
   extensions, call flows, endpoints, caller IDs, FIFO, parking,
   firewall, Configuration → {gateways, routes, templates, Settings}),
   **Asterisk** (endpoints, Configuration → {templates, Settings}).
   `connect.settings` remains a single model; each provider gets its
   own standalone settings form view + menu instead of injecting
   notebook pages into the core form.

7. **Migration path is FreeSWITCH-only.** Production has exactly one
   customer, running connect_freeswitch. Data migration scripts are
   written only for `connect` (pre-migrate: archive moved tables as
   `_*_legacy`, pattern from 19.0.3.1.0) and `connect_freeswitch`
   (post-migrate: id-preserving copy from legacy tables, Reference
   remap, `connect_user` column transfer). connect_twilio /
   connect_asterisk get no migrations — no production databases exist;
   dev bases are reinstalled. Cross-provider exten uniqueness
   disappears by design.

## Consequences

- Core `connect` no longer contains any PBX-configuration models; it
  is the call/message ledger (call, channel, recording, message),
  people (connect.user), transcription and common settings.
- `connect_crm` inherited `connect.message_configuration`; the
  extension moves to an auto-installed bridge module
  (`connect_crm_twilio`).
- The `sms.composer` inherit (raw SQL over `connect_number`) moves to
  connect_twilio.
- Duplicated code areas (exten dst mechanics, callflow language list,
  caller-ID constraints) are flagged in CLAUDE.md: change both copies.
- Versions: connect 19.0.4.0.0, connect_twilio 19.0.2.0.0,
  connect_freeswitch 19.0.2.0.0, connect_asterisk 19.0.2.0.0.
- No 18.0 backport for now (owner decision).
