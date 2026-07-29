# Connect Memory Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `connect_memory` and `connect_memory_sale` from the legacy `connect_addons` repo into `connect_addons_ng` as native modules that follow this repo's conventions.

**Architecture:** Faithful file copy of both modules (business logic unchanged), then a fixed, enumerable set of adaptations: manifest versioning (`19.0.x.y.z`), migration folder rename, security remapped to `connect.group_user`/`connect.group_admin`, XML xmlid fixes to this repo's menu/group ids, and no committed secrets. Then generate icons/descriptions, write specs/ADR/docs, and update `AGENTS.md`.

**Tech Stack:** Odoo 19 addons (Python/XML/CSV), oduflow MCP for a branch-scoped Docker test environment, `writing-odoo-module-description` skill.

## Global Constraints

- **Source paths (verbatim copy source):** `/Users/poligon/Workspace/odoo19/connect_addons/connect_memory` and `/Users/poligon/Workspace/odoo19/connect_addons/connect_memory_sale`.
- **Destination:** repo root `/Users/poligon/conductor/workspaces/connect_addons_ng/islamabad/`.
- **Python is byte-identical across series** — do NOT edit any `.py` file except `__manifest__.py` (which is data, not logic). The source already branches on `release.version_info[0] >= 19`; leave that intact.
- **Manifest version scheme:** `19.0.<product-tail>`. `connect_memory` → `19.0.1.0.1`; `connect_memory_sale` → `19.0.1.0.0`.
- **Bump manifest version at most once** — the port itself is the single release unit; do not re-bump on fix commits.
- **Commit message format:** `[connect_memory] <subject>` / `[connect_memory_sale] <subject>` / `[misc] <subject>` for cross-cutting. Lowercase imperative. NO `feat:`/`fix:`/`chore:` prefixes. Square brackets.
- **Comments in English only.**
- **Never commit `deploy/.env`** — only `.env.example` + `.gitignore`.
- **Branch is `nicolaepostica/port-connect-memory`** (non-conforming to `19.0-*`, so the `odoo_version_check` pre-commit hook skips version checks). Do NOT rename it (Conductor forbids renaming without explicit user instruction). Target base for the PR is `19.0`.
- **xmlid map (legacy → ng):** `connect.connect_top_menu` → `connect.menu_connect_root`; `connect.connect_settings_menu` → `connect.menu_connect_settings`; `connect.group_connect_admin` → `connect.group_admin`; user group is `connect.group_user`.

---

## File Structure

**`connect_memory/`** (copied, then adapted):
- `__manifest__.py` — version bumped, `images` added.
- `__init__.py`, `models/*.py`, `controllers/*.py` — copied verbatim (no edits).
- `migrations/19.0.1.0.1/post-migrate.py` — renamed folder, file verbatim.
- `security/ir.model.access.csv` — group refs remapped to Connect groups.
- `data/memory_data.xml` — copied verbatim (no group/menu refs).
- `views/memory_menus.xml`, `views/settings.xml` — xmlid/group refs fixed.
- `views/{memory_outbox,memory_inbox,memory_backfill,res_partner}_views.xml` — copied verbatim.
- `deploy/*` — copied except real `.env`.
- `tests/*` — copied verbatim.
- `static/description/{icon.png,index.html}` — generated (Task 3).

**`connect_memory_sale/`** (copied, then adapted):
- `__manifest__.py` — version bumped, `images` added.
- `__init__.py`, `models/*.py`, `data/memory_sale_data.xml`, `tests/*` — copied verbatim.
- `static/description/{icon.png,index.html}` — generated (Task 3).

**Repo-level docs/specs:**
- `specs/connect_memory.md`, `specs/connect_memory_sale.md` — new.
- `specs/decisions/043-connect-memory-outbox-inbox.md` — new ADR.
- `docs/admin/memory-setup.md`, `docs/user/memory.md` — new.
- `mkdocs.yml`, `AGENTS.md` — edited.

---

### Task 1: Port and adapt `connect_memory`

**Files:**
- Create (copy): entire `connect_memory/` tree
- Modify: `connect_memory/__manifest__.py`, `connect_memory/security/ir.model.access.csv`, `connect_memory/views/memory_menus.xml`, `connect_memory/views/settings.xml`
- Rename: `connect_memory/migrations/1.0.1/` → `connect_memory/migrations/19.0.1.0.1/`
- Delete: `connect_memory/deploy/.env`, all `__pycache__/`

**Interfaces:**
- Produces: installable module `connect_memory` exposing models `connect.memory.outbox`, `connect.memory.inbox`, `connect.memory.mixin`, `connect.memory.backfill`, `connect.memory.backfill.wizard`; `connect.settings` fields `memory_enabled`/`memory_service_url`/`memory_service_token`/`memory_default_engine`/`memory_outbox_retention_days`; controller routes `/connect_memory/{outbox,inbox}/{fetch,ack|answer}`. Registers `"connect_memory"` in `odoo.addons.connect.models.license.ODUIST_MODULES`.

- [ ] **Step 1: Copy the module tree, drop caches and the real .env**

```bash
cd /Users/poligon/conductor/workspaces/connect_addons_ng/islamabad
cp -R /Users/poligon/Workspace/odoo19/connect_addons/connect_memory ./connect_memory
find connect_memory -name '__pycache__' -type d -prune -exec rm -rf {} +
rm -f connect_memory/deploy/.env
```

- [ ] **Step 2: Rename the migration folder to the ng series version**

```bash
git -C /Users/poligon/conductor/workspaces/connect_addons_ng/islamabad mv \
  connect_memory/migrations/1.0.1 connect_memory/migrations/19.0.1.0.1 2>/dev/null \
  || mv connect_memory/migrations/1.0.1 connect_memory/migrations/19.0.1.0.1
```
(The folder is not yet tracked, so `git mv` may fail — the `||` plain `mv` handles that.)

- [ ] **Step 3: Bump the manifest version and add the icon reference**

Edit `connect_memory/__manifest__.py`:
- `'version': '1.0.1',` → `'version': '19.0.1.0.1',`
- add `'images': ['static/description/icon.png'],` immediately after the `'license': 'Other proprietary',` line.

- [ ] **Step 4: Remap security to Connect groups**

Overwrite `connect_memory/security/ir.model.access.csv` with exactly:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_memory_outbox_user,connect.memory.outbox.user,model_connect_memory_outbox,connect.group_user,1,0,0,0
access_memory_outbox_admin,connect.memory.outbox.admin,model_connect_memory_outbox,connect.group_admin,1,1,1,1
access_memory_inbox_user,connect.memory.inbox.user,model_connect_memory_inbox,connect.group_user,1,0,1,0
access_memory_inbox_admin,connect.memory.inbox.admin,model_connect_memory_inbox,connect.group_admin,1,1,1,1
access_memory_backfill_admin,connect.memory.backfill.admin,model_connect_memory_backfill,connect.group_admin,1,1,1,1
access_memory_backfill_wizard_admin,connect.memory.backfill.wizard.admin,model_connect_memory_backfill_wizard,connect.group_admin,1,1,1,1
```

- [ ] **Step 5: Fix menu xmlids + gate the memory menu on the Connect user group**

In `connect_memory/views/memory_menus.xml`:
- replace `parent="connect.connect_top_menu"` with `parent="connect.menu_connect_root"`.
- add `groups="connect.group_user"` to the `menu_memory_root` menuitem, so its final form is:

```xml
    <menuitem id="menu_memory_root" name="Memory"
              parent="connect.menu_connect_root" sequence="160"
              groups="connect.group_user"/>
```

- [ ] **Step 6: Fix the settings menu parent + admin group ref**

In `connect_memory/views/settings.xml`, on the `memory_settings_menu` menuitem:
- replace `parent="connect.connect_settings_menu"` with `parent="connect.menu_connect_settings"`.
- replace `groups="connect.group_connect_admin"` with `groups="connect.group_admin"`.

- [ ] **Step 7: Sanity-check no stale legacy xmlids remain**

Run:
```bash
grep -rn "connect_top_menu\|connect_settings_menu\|group_connect_admin\|base.group_system\|base.group_user" connect_memory/
```
Expected: no matches (empty output).

- [ ] **Step 8: Commit**

```bash
git add connect_memory
git commit -m "[connect_memory] port external AI memory module to 19.0"
```

- [ ] **Step 9: Verify install + tests in the branch environment**

Push the branch, then (oduflow MCP) `pull_and_apply`, install `connect_memory`, and run its test suite. Per the stale-template memory: on `create_environment` override `repo_url` to this repo and upgrade `connect` before installing. Env name = the branch name.
```
oduflow: pull_and_apply
oduflow: install_odoo_modules ["connect_memory"]
oduflow: run_odoo_tests connect_memory
```
Expected: module installs without ParseError/access errors; all ported tests (`test_capture`, `test_outbox`, `test_inbox`, `test_backfill`, `test_controllers`) pass.

---

### Task 2: Port and adapt `connect_memory_sale`

**Files:**
- Create (copy): entire `connect_memory_sale/` tree
- Modify: `connect_memory_sale/__manifest__.py`
- Delete: all `__pycache__/`

**Interfaces:**
- Consumes: `connect.memory.mixin` and `connect.memory.outbox` from Task 1.
- Produces: installable module `connect_memory_sale` exposing `connect.memory.sale.mixin` and capture on `sale.order`/`account.move`/`account.partial.reconcile`, plus `res.partner._memory_sale_payment_digest`. Registers `"connect_memory_sale"` in `ODUIST_MODULES`.

- [ ] **Step 1: Copy the module tree and drop caches**

```bash
cd /Users/poligon/conductor/workspaces/connect_addons_ng/islamabad
cp -R /Users/poligon/Workspace/odoo19/connect_addons/connect_memory_sale ./connect_memory_sale
find connect_memory_sale -name '__pycache__' -type d -prune -exec rm -rf {} +
```

- [ ] **Step 2: Bump the manifest version and add the icon reference**

Edit `connect_memory_sale/__manifest__.py`:
- `"version": "1.0.0",` → `"version": "19.0.1.0.0",`
- add `"images": ["static/description/icon.png"],` immediately after the `"license": "Other proprietary",` line.

- [ ] **Step 3: Sanity-check no legacy refs**

Run:
```bash
grep -rn "connect_top_menu\|connect_settings_menu\|group_connect_admin\|base.group_system" connect_memory_sale/
```
Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add connect_memory_sale
git commit -m "[connect_memory_sale] port sale/payment memory events to 19.0"
```

- [ ] **Step 5: Verify install + tests**

(oduflow MCP) `pull_and_apply`, install `connect_memory_sale` (pulls `sale`, `account`), run its tests.
```
oduflow: pull_and_apply
oduflow: install_odoo_modules ["connect_memory_sale"]
oduflow: run_odoo_tests connect_memory_sale
```
Expected: installs; `test_sale_capture`, `test_invoice_capture`, `test_payment_capture`, `test_payment_digest` pass.

---

### Task 3: Generate icons and Apps Store descriptions

**Files:**
- Create: `connect_memory/static/description/{icon.png,index.html}`
- Create: `connect_memory_sale/static/description/{icon.png,index.html}`

**Interfaces:**
- Consumes: the `images` manifest keys added in Tasks 1–2 (they reference `static/description/icon.png`).

- [ ] **Step 1: Invoke the description skill for `connect_memory`**

Use the `writing-odoo-module-description` skill (`.claude/skills/`). Point it at `connect_memory`; it carries the Oduist house style template and the code→features extraction procedure. Produce `static/description/index.html` and an `icon.png`.

- [ ] **Step 2: Invoke the description skill for `connect_memory_sale`**

Same, for `connect_memory_sale`.

- [ ] **Step 3: Verify the icon paths resolve**

```bash
ls connect_memory/static/description/icon.png connect_memory_sale/static/description/icon.png
```
Expected: both files exist (manifests already reference them).

- [ ] **Step 4: Commit**

```bash
git add connect_memory/static connect_memory_sale/static
git commit -m "[misc] add Apps Store descriptions and icons for connect_memory modules"
```

---

### Task 4: Write specs and the ADR

**Files:**
- Create: `specs/connect_memory.md`
- Create: `specs/connect_memory_sale.md`
- Create: `specs/decisions/043-connect-memory-outbox-inbox.md`

**Interfaces:**
- Consumes: the ported modules (source of truth for model/field/route lists).

- [ ] **Step 1: Write `specs/connect_memory.md`**

Follow the format of `specs/connect_bird.md` (Module Info block → Overview → Models → Controllers → Security → Views → Data/crons → Deploy sidecar). Document, from the actual code:
- Models: `connect.memory.outbox` (fields + `enqueue`/`fetch_batch`/`ack`/`_cron_vacuum_sent`, dedup on `dedup_key`+`content_hash`, the `release.version_info[0] >= 19` Constraint branch), `connect.memory.inbox` (`submit`/`claim_batch`/`store_answer`), `connect.memory.mixin` (master switch + day+module-cached license gate `_memory_emit`), `mail.thread` capture override, `connect.memory.backfill` + wizard, `res.partner` buttons.
- `connect.settings` fields + the standalone Memory form/menu.
- Controller: the four token-protected JSON-RPC routes.
- Security: `connect.group_user` read (outbox/inbox, +create on inbox); `connect.group_admin` full; backfill/wizard admin-only.
- Data: vacuum + backfill crons; `ODUIST_MODULES` registration; `post_init_hook`.
- Deploy: the `hindsight_gateway.py` sidecar (pull-based, token-auth).

- [ ] **Step 2: Write `specs/connect_memory_sale.md`**

Same format. Document `connect.memory.sale.mixin`, the `sale.order` created/lifecycle/state_change capture (tracked scalars + line diff), `account.move` posted invoice/refund, `account.partial.reconcile` payment + `late_payment` signal, `res.partner._memory_sale_payment_digest` hourly cron + `memory_payment_digest_date` cursor + the three `ir.config_parameter` knobs. Depends on `connect_memory`, `sale`, `account`; separate `ODUIST_MODULES` registration.

- [ ] **Step 3: Write ADR `043-connect-memory-outbox-inbox.md`**

Follow the format of an existing `specs/decisions/NNN-*.md`. Record: problem (bring external AI memory to Connect without coupling Odoo to any engine); options (Odoo calls the engine directly vs. an outbox/inbox pull contract vs. a message bus); decision (outbox/inbox JSONB tables; Odoo emits events and never calls the engine; an external per-engine sidecar pulls/acks; engine-neutral envelope; per-module Connect-license gate; capture never breaks the host operation). Note the domain-module pattern (`connect_memory_sale`, future `connect_memory_crm`).

- [ ] **Step 4: Commit**

```bash
git add specs/connect_memory.md specs/connect_memory_sale.md specs/decisions/043-connect-memory-outbox-inbox.md
git commit -m "[misc] add connect_memory specs and ADR-043"
```

---

### Task 5: Documentation and `AGENTS.md`

**Files:**
- Create: `docs/admin/memory-setup.md`, `docs/user/memory.md`
- Modify: `mkdocs.yml`, `AGENTS.md`

- [ ] **Step 1: Write `docs/admin/memory-setup.md`**

Admin guide: install `connect_memory` (+ `connect_memory_sale` for sales events); Connect → Configuration → Memory form (enable capture, set service URL + shared token, default engine, outbox retention days); deploy the external gateway (`connect_memory/deploy/`, `hindsight_gateway.py`, `.env.example` → `.env`, docker-compose); the pull contract (`/connect_memory/outbox/*`, `/connect_memory/inbox/*`, `X-Memory-Token`); backfilling history (per-partner button + all-partners wizard/cron). Match the tone/structure of `docs/admin/bird-setup.md`.

- [ ] **Step 2: Write `docs/user/memory.md`**

User guide: what customer memory is; the partner "Memory" smart button + "Customer summary" and "Load correspondence to memory" buttons; how answers appear (Inbox). Match the tone of an existing `docs/user/*.md`.

- [ ] **Step 3: Wire both pages into `mkdocs.yml` nav**

Add under Admin Guide (after the Bird line):
```yaml
      - Memory Setup: admin/memory-setup.md
```
Add under User Guide (after Recordings):
```yaml
      - Customer Memory: user/memory.md
```

- [ ] **Step 4: Update `AGENTS.md`**

- Add two bullets to the **Modules** list:
  - `connect_memory` — external AI memory base: `connect.memory.{outbox,inbox,mixin,backfill}` outbox/inbox pull contract + `mail.thread` correspondence capture + `res.partner` summary/backfill; provider-neutral (Hindsight/Cognee); external sidecar in `deploy/`. Depends on `connect`.
  - `connect_memory_sale` — memory events for `sale.order`/`account.move`/`account.partial.reconcile` + payment-behavior digest. Depends on `connect_memory`, `sale`, `account`.
- Add to the **Dependencies** paragraph that `connect_memory` depends on `connect`, and `connect_memory_sale` depends on `connect_memory` + `sale` + `account`.
- Add `specs/connect_memory.md` and `specs/connect_memory_sale.md` to the **Key Files** spec list.
- Add `connect_memory/tests/test_*.py` and `connect_memory_sale/tests/test_*.py` to the **Testing → Architecture** tree.
- Add `oduflow run_odoo_tests connect_memory` and `... connect_memory_sale` to the **Running Tests** list.

- [ ] **Step 5: Commit**

```bash
git add docs/admin/memory-setup.md docs/user/memory.md mkdocs.yml AGENTS.md
git commit -m "[misc] document connect_memory modules and register in AGENTS.md"
```

---

### Task 6: Full verification and PR

**Files:** none (verification + PR only).

- [ ] **Step 1: Fresh install of both modules together**

Push the branch. (oduflow MCP) on a clean env: `pull_and_apply`, then install `connect_memory` and `connect_memory_sale`. Confirm no install/upgrade errors in the tool response.

- [ ] **Step 2: Run both test suites**

```
oduflow: run_odoo_tests connect_memory
oduflow: run_odoo_tests connect_memory_sale
```
Expected: all green. Paste failing output verbatim if any; do not claim success without the passing output.

- [ ] **Step 3: UI smoke test (agent-browser)**

Reset admin password (`reset_admin_password`, env = branch), log in `admin`/`test`. Confirm: Connect → Configuration → Memory form opens and `memory_enabled` toggles; open a customer partner and confirm the "Memory" smart button + "Customer summary" / "Load correspondence to memory" header buttons render. Screenshot to `/tmp/memory_*.png` and read it back.

- [ ] **Step 4: Open the PR**

```bash
gh pr create --base 19.0 --title "Port connect_memory + connect_memory_sale" --body "<summary + test evidence>"
```
End the PR body with the Claude Code footer. Do NOT push to `19.0` directly (branch-protected).

---

## Self-Review Notes

- **Spec coverage:** Every adaptation item in the design doc maps to a task — versioning (T1/T2 step "bump"), migrations rename (T1 s2), security→Connect groups (T1 s4), XML xmlid fixes (T1 s5–s6), no-secret deploy (T1 s1), icon/description (T3), AGENTS.md/specs/docs/ADR (T4/T5), verification (T6).
- **Placeholder scan:** security CSV and xmlid edits are given verbatim; description/spec/doc bodies are content-generation tasks with explicit source-of-truth and format references (not code), which is appropriate.
- **Type consistency:** model names, route paths, and `ODUIST_MODULES` registration names are used consistently across tasks and match the source.
- **Do-not-edit-Python invariant** is called out in Global Constraints and honored — only `__manifest__.py`, CSV, and XML are edited.
