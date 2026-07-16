# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Modular telephony integration platform for Odoo with a technology-agnostic core plus provider-specific extensions.

## Modules

- **`connect`** — Technology-agnostic core: the shared call/message ledger (`connect.call`, `connect.channel`, `connect.recording`, `connect.message`), PBX people (`connect.user`), common settings, OpenAI transcription/summarization, partner integration. **Never imports provider-specific code and holds NO PBX-configuration models.**
- **`connect_twilio`** — Twilio integration. Owns its PBX configuration: `connect.twilio.{exten,callflow,callflow_choice,number,outgoing_callerid,user_callflow,message_configuration,twiml,domain}`, WhatsApp, sms.composer, webhook handlers, Twilio Voice JS SDK phone widget. **Twilio** submenu under the Connect app (incl. Messages).
- **`connect_freeswitch`** — FreeSWITCH integration. Owns `connect.freeswitch.{exten,callflow,callflow_choice,number,endpoint,outgoing_callerid}` plus gateways/routes/FIFO/parking/firewall, Verto WebRTC client, XML dialplan generation. **FreeSWITCH** submenu under the Connect app.
- **`connect_freeswitch_website`** — website widgets for FreeSWITCH number working schedules (ADR-037): Phone Status and Phone Opening Hours snippets + public JSON endpoints under `/freeswitch/schedule/*`. The only module that may depend on `website`; not auto-installed. Core `connect` owns the schedule engine (`connect.schedule` on top of `resource.calendar`).
- **`connect_asterisk`** — Asterisk integration for existing customer PBXs (FreePBX/Issabel/plain). Owns `connect.asterisk.{endpoint,number}`; AMI events arrive via a thin sidecar agent (`oduist/asterisk-agent`, `connect_asterisk/deploy/agent/`), click-to-call via AMI Originate through the agent, JsSIP web phone over WSS directly to Asterisk, config snippet generation (pjsip wizard, manager.conf). **Asterisk** submenu under the Connect app. See ADR-026.
- **`connect_telnyx`** — Telnyx integration (TeXML-first, ADR-032). Owns `connect.telnyx.{exten,callflow,callflow_choice,number,outgoing_callerid,user_callflow,message_configuration,texml,domain}`; SIP domain = credential connection + TeXML app SIP subdomain, per-user telephony credentials, @telnyx/webrtc phone widget, SMS/WhatsApp/RCS via messaging profile (ADR-033: `connect.telnyx.{whatsapp_sender,whatsapp_template,rcs_agent}` + composers), Ed25519 webhook validation. **Telnyx** submenu under the Connect app.
- **`connect_livekit`** — LiveKit integration (self-hosted realtime stack, ADR-036). Owns `connect.livekit.{room,trunk,number,outgoing_callerid,agent}`; three levels: video rooms with public guest links + Egress recording, SIP telephony via the livekit-sip bridge (BYO carrier trunk) with a browser web phone joining rooms by short-TTL JWT, and voice-AI agents served by the `oduist/livekit-agent` sidecar (LiveKit Agents, plugin cascade Deepgram/OpenAI/ElevenLabs). LiveKit webhooks (`/livekit/webhook`) verified with the JWT WebhookReceiver. **LiveKit** submenu under the Connect app; all models admin-only.
- **`connect_infobip`** — Infobip integration (event-driven Calls API, NO TwiML analog — ADR-036). Owns `connect.infobip.{exten,number,outgoing_callerid,user_callflow,message_configuration,whatsapp_sender,whatsapp_template}`; voice = webhook events → REST actions (Dialog bridges, platform-side `connectTimeout`), per-user WebRTC identities (no per-user SIP), vendored infobip-rtc phone widget, SMS + WhatsApp, recordings downloaded into attachments. No IVR/callflows in v1. **Infobip** submenu under the Connect app.
- **`connect_dograh`** — Dograh AI voice agents on FreeSWITCH (ADR-041). Owns `connect.dograh.agent`; depends on `connect` AND `connect_freeswitch`. Inbound: per-call dialplan posts Dograh's `/inbound/run` webhook and attaches mod_audio_fork (L16/16 kHz) to the returned media WebSocket; outbound: Dograh calls `/dograh/api/originate`. Ships a vendored freeswitch provider package for Dograh under `connect_dograh/deploy/` (overlay image `oduist/dograh-api`). **Dograh** submenu under the Connect app.
- **`connect_bird`** — Bird.com (ex-MessageBird) integration. Owns `connect.bird.{number,message_template,message_configuration,webhook}`; SMS/WhatsApp send/receive via the Bird developer platform (`{region}.platform.bird.com/v1`, Bearer `bk_...` keys, raw httpx — the official SDK covers only email and is not used), template-first messaging (SMS + WhatsApp templates), voice-call ledger from `voice.*` events, click-to-call via two-leg callback originate (no web phone — Bird has no WebRTC SDK), recordings fetched by cron, delivery statuses polled until the platform ships `sms.*` webhook events. Single `/bird/webhook` endpoint with Standard-Webhooks signature. **Bird** submenu under the Connect app. See ADR-038.
- **`connect_crm_twilio`** — auto-installed bridge (connect_crm + connect_twilio): message routing to CRM leads.

Dependencies: `connect_twilio`, `connect_freeswitch`, `connect_asterisk`, `connect_telnyx`, `connect_livekit`, `connect_infobip`, `connect_bird` and `connect_dograh` all depend on `connect` but are independent of each other. **Co-installation of several providers in one database is supported** (per-user `originate_provider` selects the click-to-call module, per-user `message_provider` selects the messaging module).

## Architecture

Provider model separation (ADR-031): each telephony system lives in its own
numbering plan and business logic. Extensions, numbers, call flows, caller IDs
and endpoints are **independent per-provider models** — a FreeSWITCH extension
has nothing to do with a Twilio extension. Provider modules still `_inherit`
the shared ledger models (call/channel/user/settings) to add adapter
fields/methods that normalize provider events into the common history.

```
Ledger:  _name = 'connect.call'              → shared, providers _inherit adapters
Config:  _name = 'connect.<provider>.<noun>' → fully owned by the provider module
```

**Boundary rules:**
- Core never imports `twilio` or references Twilio-specific concepts (SIDs, TwiML)
- OpenAI transcription (Whisper + GPT-4o summary) lives in core — it's provider-agnostic
- `connect.message` (ledger) stays in core; `send()` is a dispatcher like `originate_call()`: provider overrides check `_get_message_provider()` for their key and fall through to `super()` (per-user `connect.user.message_provider`). sms.composer UI and message menus live in the messaging provider modules
- `connect.settings` is a single model; each provider ships its OWN standalone settings form view + menu (opened via the parametrized `connect.settings.open_settings_form(view_xmlid, name)`) — do NOT inject notebook pages into the core form
- `connect.settings.originate_call()` is a dispatcher: provider overrides check `_get_originate_provider(user)` for their key and fall through to `super()`
- Special webhook user (`connect.user_connect_webhook`) is defined in core data, used by all integrations

> **Deliberately duplicated code (no mixins — ADR-031).** The exten
> dst-Reference mechanics and the caller-ID E.164/is_default logic exist
> as full copies in connect_twilio, connect_freeswitch, connect_telnyx
> AND connect_infobip; the BCP-47 language selection list is copied in
> the connect_twilio, connect_freeswitch and connect_telnyx callflows
> (connect_infobip has no IVR in v1) AND in core
> `connect.user._get_language_selection()` (ADR-037). When you fix or
> change one copy, apply the same change to the other modules in the
> same commit.

**Security groups:** `connect.group_user` (read), `connect.group_admin` (full CRUD), `connect.group_webhook` (webhook record creation)

> **New models — confirm Connect User access first.** When you add a new model,
> do **not** assume the `connect.group_user` access level. Stop and ask the user
> what access (none / read / read+write / own-records-only via a record rule)
> the **Connect User** group should have on it, then write the `ir.model.access`
> rows (and any `ir.rule`) accordingly. `connect.group_admin` defaults to full
> CRUD. Admin-only infrastructure/config models (e.g. `connect.settings`,
> `connect.debug`, `connect.twilio.message_configuration`, the firewall
> models) must grant the user group **no** access.

## Key Files

- `specs/architecture.md` — Authoritative design specification (boundaries, extension pattern, data flow)
- `specs/connect_core.md` — Core module spec (models, fields, methods, security, views)
- `specs/connect_twilio.md` — Twilio module spec (models, webhooks, controllers, frontend)
- `specs/connect_asterisk.md` — Asterisk module spec (models, agent contract, controllers, frontend)
- `specs/connect_telnyx.md` — Telnyx module spec (models, TeXML routing, controllers, frontend)
- `specs/connect_livekit.md` — LiveKit module spec (rooms, SIP bridge, AI agents, sidecar worker)
- `specs/connect_infobip.md` — Infobip module spec (models, event-driven voice, controllers, frontend)
- `specs/connect_dograh.md` — Dograh module spec (models, dialplan flow, controllers, vendored Dograh provider package)
- `specs/connect_freeswitch_website.md` — Website widgets module spec (snippets, public endpoints)
- `specs/connect_bird.md` — Bird module spec (models, webhooks, controllers, wizards)
- `docs/` — User and admin documentation (MkDocs Material), see `mkdocs.yml` for structure

## Development Commands
Use oduflow to manage module development and deployment.

## Version Compatibility

**Python source is identical across series branches — this is an invariant, not
a preference.** A module's `.py` files must be byte-for-byte the same on `17.0`,
`18.0` and `19.0`. This is the whole point: it turns a backport into a
near-empty diff (a clean cherry-pick instead of a manual merge), keeps review
trivial (only non-Python assets change between branches), and stops the two
series from silently drifting into two different products. Holding this
invariant is worth far more than avoiding the occasional version check.

Where Odoo genuinely behaves differently between versions, branch **inside the
same file** on `release.version_info[0]` — never fork the file per series and
never keep a series-specific copy of a `.py` file. The existing checks cover
Html field sanitize, `check_access` methods, the `Constraint` class, and the
`user_ids` attribute. On the `18.0` branch the `>= 19` arm is simply dead code
that never runs; that is expected and acceptable noise — the price you pay to
keep the file identical.

If version branching in one file grows past a couple of spots and starts to
dominate the real logic, do **not** relieve the pressure by forking the file.
Concentrate all the version-specific code in one thin compat helper/adapter that
branches internally, and have the business logic call it uniformly — the file
stays identical across branches.

**Only non-Python assets may differ between branches:** XML views, QWeb/HTML
templates, and per-series `migrations/` entry points. Everything else — models,
controllers, wizards, business logic, tests — stays identical across series.

### Cross-branch versioning rules

The same product ships on each Odoo branch; only the leading series prefix
differs. Concretely:

- **Python source is byte-identical across branches (see
  [Version Compatibility](#version-compatibility) above).** A backport touches
  only XML/HTML views and per-series `migrations/` entry points — never the
  `.py` files, which must match the source branch exactly. Version-specific
  behavior is handled by `release.version_info[0]` branching inside the shared
  file, not by forking it. If a diff between the same module on `18.0` and
  `19.0` shows differing `.py` files (beyond the manifest version string), treat
  that as drift to be reconciled, not as normal state.
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
  comments in any other language; translate existing
  non-English comments to English when you touch the surrounding code.
- Models follow `connect.<name>` naming (e.g., `connect.call`, `connect.recording`)
- Protected settings fields (API keys, tokens) are masked with `****` for non-managers
- Debug logging uses `connect.debug` model with daily cron cleanup
- Twilio webhook routes are all under `/twilio/webhook/*` and validate `X-Twilio-Signature` when enabled
- Asterisk webhook/API routes are under `/asterisk/webhook/*` and `/asterisk/api/*` and require `Authorization: Bearer <asterisk_agent_token>`
- Telnyx webhook routes are all under `/telnyx/webhook/*` and validate the Ed25519 `telnyx-signature-ed25519` header when enabled
- Infobip webhook routes are all under `/infobip/webhook/*` and require the shared `infobip_webhook_token` (`?token=` or Basic Auth password) when enabled — Infobip does not sign webhooks
- Dograh control routes are all under `/dograh/api/*` and require `Authorization: Bearer <dograh_service_token>` (fail-closed; the same shared secret authenticates Odoo→Dograh inbound webhooks)
- Bird events arrive on the single `/bird/webhook` route and validate the Standard-Webhooks signature (`webhook-id` / `webhook-timestamp` / `webhook-signature`, `whsec_` secret) when enabled
- Frontend assets: Twilio phone widget in `connect_twilio/static/src/`, Verto client in `connect_freeswitch/static/src/`, JsSIP web phone in `connect_asterisk/static/src/`, Telnyx WebRTC phone in `connect_telnyx/static/src/`, LiveKit web phone in `connect_livekit/static/src/`, Infobip WebRTC phone in `connect_infobip/static/src/`
- **Module Apps Store descriptions** (`<module>/static/description/index.html`)
  follow the fixed Oduist house style. To write or regenerate one, use the
  `writing-odoo-module-description` skill (`.claude/skills/`), which carries the
  template and the code→features extraction procedure.

## FreeSWITCH & Firewall Docker Images

- FreeSWITCH image: `oduist/freeswitch` — Dockerfile: `connect_freeswitch/deploy/Dockerfile`, config: `connect_freeswitch/deploy/freeswitch/conf/`
- Firewall image: `oduist/freeswitch-firewall` — Dockerfile: `connect_freeswitch/deploy/firewall/Dockerfile`, sources: `connect_freeswitch/deploy/firewall/src/`
- Asterisk agent image: `oduist/asterisk-agent` — Dockerfile: `connect_asterisk/deploy/agent/Dockerfile`, sources: `connect_asterisk/deploy/agent/src/`. Same versioning policy: rebuilt only when a release changes files under `connect_asterisk/deploy/agent/`; tag = short `connect_asterisk` manifest version; build multi-arch (`linux/amd64,linux/arm64`) — the agent runs on customer hardware.
- LiveKit agent image: `oduist/livekit-agent` — Dockerfile: `connect_livekit/deploy/agent/Dockerfile`, sources: `connect_livekit/deploy/agent/src/`. One image, two commands (`run` = LiveKit Agents worker, `upload-recordings` = egress uploader). Same versioning policy: rebuilt only when a release changes files under `connect_livekit/deploy/agent/`; tag = short `connect_livekit` manifest version; build multi-arch (`linux/amd64,linux/arm64`) — the worker runs on customer hardware. The LiveKit server/sip/egress images in `connect_livekit/deploy/docker-compose.yml` are pinned upstream `livekit/*` images.

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

# Testing

## Architecture

Tests live next to the module they cover, under `<module>/tests/`, and are
committed in the main repository with the implementation they verify.

```
connect_addons_ng/
├── connect/tests/test_*.py
├── connect_twilio/tests/test_*.py
├── connect_freeswitch/tests/test_*.py
├── connect_asterisk/tests/test_*.py
├── connect_crm/tests/test_*.py
├── connect_telnyx/tests/
├── connect_infobip/tests/test_*.py
├── connect_bird/tests/test_*.py
├── connect_dograh/tests/test_*.py
└── connect_helpdesk/tests/
```

Every populated test package has a plain `tests/__init__.py` with explicit
imports for each `test_*.py` file:

```python
from . import test_call
from . import test_settings
```

Helper modules such as `common.py` stay in the same `tests/` package and can be
imported with normal relative imports (`from .common import BaseCase`).

## Agent Behavior

- When writing or changing tests, place them in the owning module's `tests/`
  directory, not in a shared test repository.
- Add every new `test_*.py` file to that module's `tests/__init__.py`.
- Keep tests and implementation in the same feature branch and pull request.
- Do not create test submodules, gitlinks, dynamic import loaders, or manual
  test-copy steps.

## Adding Tests to a Module

When creating tests for a module that has no tests yet:

1. Create `<module>/tests/__init__.py`.
2. Add one or more `<module>/tests/test_*.py` files.
3. Import each test module from `<module>/tests/__init__.py`.

## Running Tests

Use oduflow to run Odoo tests in the target environment. In the normal
`repo_url` workflow, commit and push the branch first, then call
`pull_and_apply`, then run tests:

```bash
oduflow run_odoo_tests connect
oduflow run_odoo_tests connect_twilio
oduflow run_odoo_tests connect_freeswitch
oduflow run_odoo_tests connect_asterisk
oduflow run_odoo_tests connect_crm
oduflow run_odoo_tests connect_telnyx
oduflow run_odoo_tests connect_infobip
oduflow run_odoo_tests connect_dograh
oduflow run_odoo_tests connect_helpdesk
```

`run_odoo_tests` runs tests through Odoo's normal module test discovery, so the
module must already be installed in the environment. If a module is not
installed, install or upgrade it through the normal oduflow module workflow
before testing.

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
