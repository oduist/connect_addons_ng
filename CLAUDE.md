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
- `docs/` — User and admin documentation (MkDocs Material), see `docs/mkdocs.yml` for structure

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

## FreeSWITCH Docker Image

- Image: `oduist/freeswitch`
- Dockerfile: `connect_freeswitch/deploy/Dockerfile`
- Config files: `connect_freeswitch/deploy/freeswitch/conf/`

**Workflow** when changing FreeSWITCH config or Dockerfile:
1. Increment version in `connect_freeswitch/__manifest__.py` (e.g. `19.0.1.0.2` → `19.0.1.0.3`)
2. Build image using the short version (strip Odoo prefix): `docker build --platform linux/amd64 --provenance=false --sbom=false -t oduist/freeswitch:1.0.3 -t oduist/freeswitch:latest connect_freeswitch/deploy/`
3. Push both tags: `docker push oduist/freeswitch:1.0.3 && docker push oduist/freeswitch:latest`

## Decision Log (ADR)

Architecture Decision Records are stored in `specs/decisions/`. Each file documents one decision: the problem, options considered, and chosen approach with rationale.

**Format:** `NNN-short-title.md` (e.g. `001-freeswitch-log-levels.md`)

**Workflow:** Every development session must start in plan mode. The plan produces an ADR entry before implementation begins. This ensures design decisions are captured with their context while it's fresh.

## Documentation & Specs Maintenance

When making code changes, **always** keep these in sync:

1. **User documentation** (`docs/user/`) — Update if the change affects what users see or do (UI, workflows, features)
2. **Admin documentation** (`docs/admin/`) — Update if the change affects installation, configuration, or infrastructure
3. **Specifications** (`specs/`) — Update if the change affects models, fields, methods, security, controllers, or architecture

If a code change adds, removes, or modifies a feature, the corresponding documentation and spec files must be updated in the same commit.
