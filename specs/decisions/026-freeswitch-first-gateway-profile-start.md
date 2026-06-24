# ADR-026: First gateway creation must start (not just restart) the external sofia profile

## Status
Accepted

## Context

When the very first `connect.freeswitch.gateway` is created on a fresh
deployment, `FreeSwitchGateway.create()` calls `_reload_sofia_profile()`, which
told FreeSWITCH to `sofia profile external restart reloadxml`
(`models/gateway.py`). On a fresh box the `external` sofia profile has **never
been started** — the static `autoload_configs/sofia.conf.xml` ships an empty
`<profiles/>` and every profile is served on demand from Odoo via
`mod_xml_curl`. `mod_sofia` treats `restart` of a not-yet-loaded profile as a
silent no-op, so the profile never comes up and the gateway never registers
until an operator manually runs `fs_cli -x "sofia profile external start"`. A
fresh REISO/sozialinfo deployment hit exactly this and required manual
intervention (issue #38).

There are **two** root causes, and a correct fix must close both:

1. **No-op restart.** `restart` does nothing when the profile is absent; the
   first creation needs `start`.

2. **Transaction-visibility race.** The profile configuration is fetched by
   FreeSWITCH in a **separate** HTTP request to
   `controllers/freeswitch_xml.py::_get_sofia_config` — a different cursor /
   transaction. `start`/`restart` trigger that xml_curl fetch synchronously.
   But `_reload_sofia_profile()` ran *inside* `create()`, **before** the
   transaction committed. Under PostgreSQL `READ COMMITTED`, the xml_curl
   request cannot see the uncommitted gateway, so `_get_sofia_config` finds no
   active gateways and returns `_not_found()` — FreeSWITCH gets an empty config
   and the profile starts without the gateway (or not at all). This is why the
   *manual* `start` works (the row is committed by then) but a synchronous
   `start` issued from `create()` would not reliably help. The same race
   applies to `_reload_acl()`, whose `gateways` ACL is also served via
   xml_curl.

The module already has an idiom for "notify FreeSWITCH after our DB write is
durable": `models/firewall.py::_trigger_sync` schedules its HTTP POST with
`self.env.cr.postcommit.add(...)`.

## Decision

Defer the reload to **post-commit** and **start the profile when it is not
loaded yet**:

1. **Post-commit deferral.** `_reload_sofia_profile()` and `_reload_acl()` no
   longer call `freeswitch_api` synchronously; they schedule the work via
   `self.env.cr.postcommit.add(...)`, reusing the firewall idiom. The callback
   runs after the gateway row is committed, so FreeSWITCH's xml_curl fetch sees
   it. The callbacks are bound to the **model** (`self.env['connect.freeswitch.
   gateway']._apply_sofia_profile_reload`), not the affected recordset, so they
   work correctly after `unlink()` too — they re-read config from the DB and do
   not touch the deleted records.

2. **Status-check start/restart.** `_apply_sofia_profile_reload` first queries
   `sofia status profile external`. `mod_sofia` answers `Invalid Profile!` for
   an unknown profile, so when the response is falsy (XML-RPC unreachable) or
   contains `Invalid Profile`, it sends `sofia profile external start`;
   otherwise it sends `sofia profile external restart reloadxml`. `start`
   triggers the now-committed xml_curl fetch and brings the profile up with the
   gateway; `restart reloadxml` applies later edits to an already-running
   profile.

`create`/`write`/`unlink` are unchanged — they still call
`_reload_sofia_profile()` / `_reload_acl()`; only those methods' timing moved to
post-commit.

## Alternatives considered

- **Synchronous start/restart branching only (the issue's literal
  recommendation).** Adds the `start` branch but keeps the reload inside
  `create()`. Rejected: it leaves the transaction-visibility race (cause #2)
  open — on the very first creation the synchronous xml_curl fetch can still
  read an uncommitted (invisible) gateway and return an empty config, so the
  profile may come up without the gateway. Post-commit is required for the fix
  to actually work on a fresh deploy.

- **Unconditional `start` then `restart reloadxml` (the issue's option 2).**
  Avoids parsing the status string but issues a redundant `restart` on every
  edit and logs a benign `Profile [external] already started` warning in the
  FreeSWITCH log each time. The status-check is cleaner — one heavy operation,
  no warning noise — at the cost of a substring match on `Invalid Profile`,
  which is `mod_sofia`'s stable response for an unknown profile.

- **Auto-start the external profile at FreeSWITCH boot (entrypoint / static
  config).** Rejected: the profile config is intentionally dynamic (served from
  Odoo); starting it at boot would race Odoo availability and duplicate the
  xml_curl-driven model. The reload-on-change path is the right place to ensure
  the profile is up.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same fix ports to the `18.0` branch with
the aligned tail version: `connect_freeswitch` moves `19.0.1.10.1 →
19.0.1.10.2` and `18.0.1.10.1 → 18.0.1.10.2`. No schema change, so no migration
script is required. The backport ships as a separate PR.
