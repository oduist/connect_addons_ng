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

### Cross-branch versioning rules

The same product ships on each Odoo branch; only the leading series prefix
differs. Concretely:

- **Manifest versions are aligned across branches.** If a module is at
  `19.0.1.8.13` on the `19.0` branch, the same module on the `18.0`
  branch must be at `18.0.1.8.13` once the corresponding change is
  ported. The tail (`1.8.13`) is the product version; the head (`19.0`,
  `18.0`) only marks the target Odoo series.
- **Each branch keeps only its own series migrations.** The `18.0` branch
  carries `migrations/18.0.x.x.x/`, the `19.0` branch carries
  `migrations/19.0.x.x.x/`. Do not leave migration folders for other
  Odoo series sitting in a branch — they never run there and only
  confuse readers.
- **Backports use the same Python helpers.** When the change involves a
  Python migration script, both branches should call the same module
  function (e.g. `setup_firewall(env)`), with the per-series migration
  folder acting purely as the entry point Odoo can match.

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

## Testing FreeSWITCH SIP Calls

Use oduflow's `run_service_command` to execute `fs_cli` commands directly inside the FreeSWITCH container — no external SIP client needed.

```bash
# Originate a test call (echo app mirrors audio back)
fs_cli -x "originate sofia/internal/1000@localhost &echo"

# Check SIP registration status
fs_cli -x "sofia status profile internal"

# Show active calls
fs_cli -x "show calls"
```

Use `get_service_logs` to check FreeSWITCH logs after originating calls.

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

# Testing — Gated Test Suite

## Architecture

Tests live in a **private git submodule** (`tests_suite/`), separate from the business logic:

```
connect_addons_ng/              ← Main repo (public)
├── connect/
│   └── tests → ../tests_suite/connect/tests          (symlink)
├── connect_twilio/
│   └── tests → ../tests_suite/connect_twilio/tests    (symlink)
├── connect_freeswitch/
│   └── tests → ../tests_suite/connect_freeswitch/tests (symlink)
└── tests_suite/                ← Private submodule (oduist/connect_addons_tests)
    ├── connect/tests/
    ├── connect_twilio/tests/
    └── connect_freeswitch/tests/
```

## Operating Modes

**Unprotected Mode** — The `tests_suite` submodule is not initialized. Symlinks are broken, `tests/` directories are empty. Code can be modified but not verified. A missing `tests/` folder is NOT an error — it means the test suite license is not active.

**Safe Mode** — The `tests_suite` submodule is initialized. Symlinks resolve. Use tests as the primary success criterion for every task.

## Agent Behavior

- **Always check** if `tests_suite/` is populated before attempting to run tests.
- **Never treat** a missing or broken `tests/` symlink as a bug.
- **In Safe Mode**: run tests after every code change. Tests are the gatekeeper.
- **In Unprotected Mode**: rely on manual verification and code review.
- **When writing new tests**: place them in `tests_suite/<module>/tests/`, not directly in the module.

## Adding a New Module to the Test Suite

When creating a new module (e.g., `connect_crm`):

1. Create the test scaffold in the submodule: `tests_suite/connect_crm/tests/__init__.py`
2. Create a symlink from inside the module: `cd connect_crm && ln -s ../tests_suite/connect_crm/tests tests`
3. Commit the symlink to the main repo and the scaffold to `tests_suite`

## Running Tests

```bash
# Setup symlinks (one-time, after cloning)
git submodule update --init

# Run tests via oduflow
oduflow run_odoo_tests connect
oduflow run_odoo_tests connect_twilio
oduflow run_odoo_tests connect_freeswitch
```

## Self-driven verification of changes

When a change can realistically be checked in the UI, verify it yourself — do not delegate the check to the user.

### Resetting the admin password in an oduflow environment

Call `mcp__oduflow_velesagro__reset_admin_password` with `env_name = <current branch name>`. After reset: login `admin`, password `test`.

### UI tests via agent-browser

Use the `agent-browser` skill (available locally) for scenarios like "open a form / click / type / check result". Typical cycle:

1. `agent-browser open <environment URL>` — URL from the `create_environment` response or `list_environments`.
2. Log in (`admin` / `test` after password reset).
3. `agent-browser snapshot -i` → act via `@eN` refs. After any action that changes the page (navigation, submit, opening a dialog), take a **new snapshot** — refs become stale.
4. For elements that do not appear in the a11y snapshot (Odoo autocomplete, jQuery UI popups), use `agent-browser eval --stdin` with a short JS query.
5. `agent-browser screenshot /tmp/<name>.png` + read the file via `Read` to visually confirm the result.
6. At the end — `agent-browser close`.

### When a UI test does not apply

Server-side / background changes with no visual effect — verify through `run_odoo_shell`, `run_odoo_tests`, `http_request_to_odoo`. Module install/upgrade logs are read directly from the response of the corresponding MCP tool; `get_environment_logs` is for runtime errors during request handling only.
