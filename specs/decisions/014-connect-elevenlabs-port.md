# ADR-014: Port connect_elevenlabs* suite to new architecture

**Status:** Accepted
**Date:** 2026-04-24

## Context

Four ElevenLabs modules exist in the old monolithic repo `/workspace/odoo19/addons_connect/`:

| Module | Depends | Scope |
|---|---|---|
| `connect_elevenlabs` | `connect`, `calendar`, py `elevenlabs` | Conversational-AI agents, voices, tools, TTS files, post-call + transfer + calendar webhooks, transcription provider, IVR/voicemail TTS |
| `connect_elevenlabs_helpdesk` | `connect_elevenlabs`, `connect_helpdesk` | Ticket create/search tools |
| `connect_elevenlabs_knowledge` | `connect_elevenlabs` | Knowledge-base docs tied to agents |
| `connect_elevenlabs_sale` | `connect_elevenlabs`, `sale_management` | Sale-specific call data + tools |

These have to be ported to the new split architecture (`connect` core + `connect_twilio` + `connect_freeswitch`). The new core is technology-agnostic: it does not import `twilio`, and the `connect.settings.get_client()` Twilio REST factory and `connect.twiml` helpers now live in `connect_twilio`, not in core.

The old `connect_elevenlabs` is Twilio-coupled:

- `agent.render()` emits `<Connect><Stream url=…>` TwiML.
- `agent.transfer()` drives `client.calls(sid).update(twiml=…)` (Twilio REST).
- `number.route_call()` returns TwiML.
- `callflow` / `user` TTS playback is TwiML `Gather.play()` / `response.play()`.
- Imports `from odoo.addons.connect.models.twiml import pretty_xml` — that module now lives under `connect_twilio`.
- The media-bridge FastAPI service terminates Twilio Media Streams.

Nothing in the source references FreeSWITCH; `mod_audio_fork`-based FreeSWITCH support is explicitly out of scope for this sprint.

## Options

1. **Split into `connect_elevenlabs` (agnostic) + `connect_elevenlabs_twilio` (glue).** Cleanest architectural fit. Requires inventing a second module without a FreeSWITCH counterpart yet, adds indirection for tests and deployment, and doubles the porting surface.
2. **Port `connect_elevenlabs` as a single Twilio-dependent module.** Same boundary as the source. Add `connect_twilio` to its `depends` so TwiML and Twilio REST imports resolve. No architectural invention ahead of need.
3. **Fold `_helpdesk`, `_knowledge`, `_sale` into the main module.** Rejected upstream — keep them separate for licensing and install-time optionality.

## Decision

Option **2**: port the four modules separately, preserving the source boundary, with `connect_elevenlabs` depending on `connect_twilio`. No speculative `connect_elevenlabs_twilio` glue module until a FreeSWITCH counterpart justifies one.

### Module layout

```
connect_elevenlabs/                 depends: connect, connect_twilio, calendar
connect_elevenlabs_helpdesk/        depends: connect_elevenlabs, connect_helpdesk
connect_elevenlabs_knowledge/       depends: connect_elevenlabs
connect_elevenlabs_sale/            depends: connect_elevenlabs, sale_management
```

`connect_elevenlabs` keeps its media-bridge FastAPI service under `service/` (Docker deployable). Twilio Media Streams stay the only transport.

### Changes during port

1. **Import swap:** `from odoo.addons.connect.models.twiml import pretty_xml` → `from odoo.addons.connect_twilio.models.twiml import pretty_xml`.
2. **License registry:** each module appends itself to `ODUIST_MODULES` in its own `settings.py`. `check_license()` call sites preserved from the source.
3. **`PROTECTED_FIELDS`:** add `display_elevenlabs_api_key`, `display_elevenlabs_post_call_webhook_secret` to the core `PROTECTED_FIELDS` list via `settings.py` import.
4. **Settings view:** moves to an ElevenLabs notebook tab added via view inheritance on the core settings form (per `specs/architecture.md §Settings Architecture`).
5. **Drop `PAGE_MAP` injection:** no centralized documentation PAGE_MAP exists in the new architecture; `documentation.py` is removed.
6. **`connect.channel.sid`:** already generic in new core — no remapping needed.
7. **Tests:** each module adds a `tests/` symlink into `tests_suite/connect_elevenlabs*/tests/` (gated-test-suite pattern per ADR-011).

### Features deferred

- `connect_elevenlabs_freeswitch` glue + `mod_audio_fork` media bridge — not in this sprint.
- Dynamic ElevenLabs-side consumer registration for queues — not in scope.

## Consequences

- `connect_elevenlabs` is a Twilio-dependent module on the new architecture. This is accepted: a clean agnostic split can happen when a FreeSWITCH implementation is actually written.
- The four modules match the source 1:1, keeping porting mechanical and reducing risk.
- Licensing and install-time optionality are preserved for `_helpdesk`, `_knowledge`, `_sale` buyers.
- Docs get two new pages (`docs/admin/elevenlabs-setup.md`, `docs/user/elevenlabs-agents.md`) registered in `docs/mkdocs.yml`.
- Specs get four new files (`specs/connect_elevenlabs.md`, `specs/connect_elevenlabs_helpdesk.md`, `specs/connect_elevenlabs_knowledge.md`, `specs/connect_elevenlabs_sale.md`).
