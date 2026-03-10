# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Modular telephony integration platform for Odoo with a technology-agnostic core plus provider-specific extensions.

## Modules

- **`connect`** — Technology-agnostic core. Stores calls, messages, recordings, users, callflows, extensions. Handles OpenAI transcription/summarization, SMS composer UI, partner integration. **Never imports provider-specific code.**
- **`connect_twilio`** — Twilio integration. Extends core models via `_inherit`. Adds TwiML apps, SIP domains, WhatsApp, webhook handlers, Twilio Voice JS SDK phone widget.
- **`connect_freeswitch`** — FreeSWITCH integration. Adds Verto WebRTC client, XML dialplan generation, endpoint management.

Dependencies: `connect_twilio` and `connect_freeswitch` both depend on `connect` but are independent of each other.

## Architecture

The core design pattern: core defines abstract interfaces, integration modules implement them via `_inherit`.

```
Core:   _name = 'connect.foo'     → abstract methods (raise NotImplementedError or pass)
Twilio: _inherit = 'connect.foo'  → implements abstract methods, adds provider fields
```

**Boundary rules:**
- Core never imports `twilio` or references Twilio-specific concepts (SIDs, TwiML)
- OpenAI transcription (Whisper + GPT-4o summary) lives in core — it's provider-agnostic
- SMS composer lives in core with abstract `send()` — integration modules implement it
- Settings form uses notebook tabs; each integration adds its own page via view inheritance
- Special webhook user (`connect.user_connect_webhook`) is defined in core data, used by all integrations

**Security groups:** `connect.group_user` (read), `connect.group_admin` (full CRUD), `connect.group_webhook` (webhook record creation)

## Key Files

- `specs/architecture.md` — Authoritative design specification (boundaries, extension pattern, data flow)
- `specs/connect_core.md` — Core module spec (models, fields, methods, security, views)
- `specs/connect_twilio.md` — Twilio module spec (models, webhooks, controllers, frontend)
- `docs/connect_migrate.md` — Migration guide from monolithic to modular architecture

## Development Commands
Use oduflow to manage module development and deployment.

## Version Compatibility

Code includes `release.version_info[0]` checks to support Odoo 17.0, 18.0, and 19.0 differences (Html field sanitize, check_access methods, Constraint class, user_ids attribute).

## Conventions

- Models follow `connect.<name>` naming (e.g., `connect.call`, `connect.recording`)
- Protected settings fields (API keys, tokens) are masked with `****` for non-managers
- Debug logging uses `connect.debug` model with daily cron cleanup
- Twilio webhook routes are all under `/twilio/webhook/*` and validate `X-Twilio-Signature` when enabled
- Frontend assets: Twilio phone widget in `connect_twilio/static/src/`, Verto client in `connect_freeswitch/static/src/`
