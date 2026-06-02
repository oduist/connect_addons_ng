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
- **Clean up the backport branch as soon as the PR is open.** After
  `gh pr create` returns the backport PR URL, automatically:
  1. `git worktree remove <path>` if a worktree was used for the port;
  2. `git branch -D <port-branch>` to drop the local ref;
  3. leave the remote branch in place — it backs the PR and GitHub
     deletes it on merge (repo has "Automatically delete head branches"
     enabled).
  Do this without asking; treat it as part of the backport workflow.

### Bump the manifest version at most once per session / feature branch

A `__manifest__.py` `version` bump represents one logical release unit
of the module — the same unit that ships as one PR. **Bump it at most
once per working session / feature branch, regardless of how many
intermediate fix commits the branch contains.** Multiple bumps within
one branch are wrong: they produce noisy history, force you to flatten
versions before merge, and have no functional effect.

Specifically:
- Do **not** bump the version on every commit. Bug-fix commits in
  controllers / models / data are picked up by `pull_and_apply` via
  diff analysis (Python → restart, schema/field change → upgrade,
  views/assets → hot-reload); none of these require the manifest to
  change.
- Do **not** create a standalone "chore: bump version" commit. If the
  bump is needed for a release, fold it into the last functional
  commit or a single cleanup commit at the end of the branch.
- The version moves on **release boundaries**, not on commit
  boundaries. Inside one session the bump should land once — typically
  in the first commit that changes module behavior, or in a final
  cleanup pass just before opening the PR.
- If you realise mid-session that you already bumped the version,
  leave it alone and keep working at that target version; do not bump
  again.

## Conventions

- **Always write comments in English.** This applies to all source and
  config files (Python, JS, XML, YAML, Dockerfiles, etc.). Do not leave
  comments in Russian or any other language; translate existing
  non-English comments to English when you touch the surrounding code.
- Models follow `connect.<name>` naming (e.g., `connect.call`, `connect.recording`)
- Protected settings fields (API keys, tokens) are masked with `****` for non-managers
- Debug logging uses `connect.debug` model with daily cron cleanup
- Twilio webhook routes are all under `/twilio/webhook/*` and validate `X-Twilio-Signature` when enabled
- Frontend assets: Twilio phone widget in `connect_twilio/static/src/`, Verto client in `connect_freeswitch/static/src/`

## FreeSWITCH & Firewall Docker Images

- FreeSWITCH image: `oduist/freeswitch` — Dockerfile: `connect_freeswitch/deploy/Dockerfile`, config: `connect_freeswitch/deploy/freeswitch/conf/`
- Firewall image: `oduist/freeswitch-firewall` — Dockerfile: `connect_freeswitch/deploy/firewall/Dockerfile`, sources: `connect_freeswitch/deploy/firewall/src/`

### Versioning policy

The image tag is **decoupled** from both the upstream FreeSWITCH version and from the `connect_freeswitch` module version. Images are **not rebuilt on every manifest bump** — only when a release actually changes files under `connect_freeswitch/deploy/` (FreeSWITCH) or `connect_freeswitch/deploy/firewall/` (firewall service).

As a result, the published image tags **lag behind** the module manifest version. That is expected. When a module release happens to coincide with a deploy-folder change, the new image tag will match the current short manifest version — and that match acts as a useful sync marker, not a contract.

### Workflow when changing files under `connect_freeswitch/deploy/`

1. Read the current version from `connect_freeswitch/__manifest__.py` (e.g. `19.0.1.10.4`).
2. Strip the leading `19.0.` (Odoo series) prefix → short version (e.g. `1.10.4`).
3. Build and push using that short version:
   - FreeSWITCH (deploy folder changed):
     ```
     docker build --platform linux/amd64 --provenance=false --sbom=false \
       -t oduist/freeswitch:<short> -t oduist/freeswitch:latest \
       connect_freeswitch/deploy/
     docker push oduist/freeswitch:<short> && docker push oduist/freeswitch:latest
     ```
   - Firewall (firewall folder changed):
     ```
     docker build --platform linux/amd64 --provenance=false --sbom=false \
       -t oduist/freeswitch-firewall:<short> -t oduist/freeswitch-firewall:latest \
       connect_freeswitch/deploy/firewall/
     docker push oduist/freeswitch-firewall:<short> && docker push oduist/freeswitch-firewall:latest
     ```
4. The two images are independent — only rebuild the one whose source files actually changed in this release.

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

Tests live in a **private git submodule** (`tests_suite/`), separate from the business logic. Each addon ships a tracked `tests/__init__.py` that conditionally pulls `test_*.py` from the submodule at import time:

```
connect_addons_ng/              ← Main repo (public)
├── connect/
│   └── tests/__init__.py       ← conditional loader (tracked)
├── connect_twilio/
│   └── tests/__init__.py       ← conditional loader (tracked)
├── connect_freeswitch/
│   └── tests/__init__.py       ← conditional loader (tracked)
└── tests_suite/                ← Private submodule (oduist/connect_addons_tests)
    ├── connect/tests/test_*.py
    ├── connect_twilio/tests/test_*.py
    └── connect_freeswitch/tests/test_*.py
```

The loader checks `os.path.isdir("../../tests_suite/<addon>/tests")`. When present, it dynamically loads each `test_*.py` via `importlib.util.spec_from_file_location` and registers it as a submodule of `<addon>.tests`. When absent, the loader is a no-op — the addon installs cleanly with no tests.

## Operating Modes

**Unprotected Mode** — The `tests_suite` submodule is not initialized. The loader sees no `tests_suite/` directory and exposes an empty `tests` package. Code can be modified but not verified. A missing `tests_suite/` is NOT an error — it means the test suite license is not active.

**Safe Mode** — The `tests_suite` submodule is initialized. The loader registers all `test_*.py` files. Use tests as the primary success criterion for every task.

## Submodule init policy

`.gitmodules` carries `update = none` for `tests_suite`. This makes the default `git submodule update --init` (and `uv sync`'s `git submodule update --init --recursive`) silently skip the private submodule, so external users without access can clone the repo and build addons as uv dependencies.

Internal developers who need tests initialize the submodule explicitly:

```bash
git -c submodule.tests_suite.update=checkout submodule update --init tests_suite
```

## Agent Behavior

- **Always check** if `tests_suite/` is populated before attempting to run tests.
- **Never treat** a missing `tests_suite/` as a bug.
- **In Safe Mode**: run tests after every code change. Tests are the gatekeeper.
- **In Unprotected Mode**: rely on manual verification and code review.
- **When writing new tests**: place them in `tests_suite/<module>/tests/`, not directly in the module.

## Adding a New Module to the Test Suite

When creating a new module (e.g., `connect_crm`):

1. Create the test scaffold in the submodule: `tests_suite/connect_crm/tests/__init__.py`
2. Create `connect_crm/tests/__init__.py` in the main repo — copy the loader from `connect/tests/__init__.py` and change the `_SUITE` path to `connect_crm`.
3. Commit both files.

## Note on relative imports in tests

The loader registers each `test_*.py` individually via `importlib.util.spec_from_file_location`. Modules are formally part of `<addon>.tests` but physically live in `tests_suite/`. As a consequence, **relative imports between test modules will not work** (e.g. `from . import helpers` inside `test_foo.py`).

Today this is not a problem — `tests_suite` only contains `test_firewall.py` with no helpers. If helper modules become necessary:

- **Preferred:** use absolute imports (`from tests_suite.<addon>.tests import helpers`).
- **Alternative:** extend the loader to do a two-pass load — first non-`test_*` modules (helpers), then `test_*` ones.

## Running Tests

```bash
# Setup tests (one-time, after cloning) — requires tests_suite access
git -c submodule.tests_suite.update=checkout submodule update --init tests_suite

# Run tests via oduflow
oduflow run_odoo_tests connect
oduflow run_odoo_tests connect_twilio
oduflow run_odoo_tests connect_freeswitch
```

## Installing as a uv dependency (external consumers)

External users can install individual addons without access to `tests_suite`:

```bash
uv pip install "odoo-addon-connect @ git+https://github.com/oduist/connect_addons_ng.git@19.0#subdirectory=connect"
uv pip install "odoo-addon-connect-twilio @ git+https://github.com/oduist/connect_addons_ng.git@19.0#subdirectory=connect_twilio"
uv pip install "odoo-addon-connect-freeswitch @ git+https://github.com/oduist/connect_addons_ng.git@19.0#subdirectory=connect_freeswitch"
```

Replace `@19.0` with `@18.0` for the Odoo 18 series. Tests are not available in this mode.

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
