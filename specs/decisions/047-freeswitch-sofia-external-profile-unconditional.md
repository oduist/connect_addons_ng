# ADR-047: Always serve the sofia `external` profile, even with no gateways

## Status
Accepted

## Context

The `external` sofia profile is served on demand from Odoo via `mod_xml_curl`
(`connect_freeswitch/controllers/freeswitch_xml.py::_get_sofia_config`) — the
static `autoload_configs/sofia.conf.xml` ships an empty `<profiles/>`. SIP
endpoints register against `external` and outbound legs are bridged via
`sofia/external/sip:…`, so the profile must exist independently of whether any
outbound **gateway** (SIP trunk) record exists.

`_get_sofia_config` gated the whole response on gateways:

```python
if not gateways:
    return self._not_found()
```

On a fresh env with no `connect.freeswitch.gateway` records, Odoo answered the
`sofia.conf` xml_curl request with `<result status="not found"/>`. FreeSWITCH
therefore got **no** sofia configuration at all and the `external` profile could
not start:

- `sofia status` → `0 profiles`
- `sofia profile external start` → `Failure starting external`

No SIP registration was possible; only the Verto (WebRTC) profile, which is
served separately, kept working — so browser calls looked fine while the entire
SIP side was dead. Reported on a fresh deployment (ODU-45).

The gate was a regression on the `19.0` line: the sibling
`19.0-twilio-fs-compat` branch already rendered the profile unconditionally. The
template (`data/fs_templates.xml::config_sofia`) always renders the full
`<profile name="external">` and injects `{{ gateways_xml }}` (empty when there
are none), so the gate was the only thing suppressing an otherwise valid config.

## Decision

Drop the `if not gateways: return self._not_found()` gate. `_get_sofia_config`
now **always** renders the `external` profile; gateways are joined into the
profile only when present (empty string otherwise). A fresh env therefore serves
a valid `sofia.conf`, and the `external` profile starts and accepts
registrations without any gateway, DID, or firewall record.

This does **not** revert ADR-028: the post-commit deferral of
`_reload_sofia_profile()` / `_reload_acl()` is still required so that a
newly-created gateway is committed (and thus visible to the separate xml_curl
cursor) before FreeSWITCH re-fetches the profile. ADR-047 only removes the
"empty config when zero gateways" failure mode; ADR-028 continues to govern the
reload timing and the `start`-vs-`restart` status check.

## Alternatives considered

- **Auto-start `external` from static config at FreeSWITCH boot.** Rejected for
  the same reason as in ADR-028: the profile config is intentionally dynamic
  (served from Odoo) and booting it statically races Odoo availability and
  duplicates the xml_curl-driven model.

- **Keep the gate but return a gateway-less profile only when endpoints/DIDs
  exist.** Rejected: the `external` profile is the SIP-registration surface and
  must be up on a bare env before any endpoint is configured; conditioning it on
  other records reintroduces the same class of "profile absent on fresh env"
  bug.

## Consequences

- Regression coverage: `connect_freeswitch/tests/test_sofia_config.py`
  (`section=configuration`, `key_value=sofia.conf` over `/freeswitch/xml`) —
  asserts the profile is served with zero gateways and that a gateway is
  injected when one exists.
- No schema change, so no migration script is required.

## Cross-branch backport

Per `AGENTS.md` versioning rules the same fix ports to `18.0` with the aligned
tail version (Python source stays byte-identical). The `18.0` branch still
carries the gate and needs the port.

## History

Originally proposed as PR #137 (branch `19.0-sofia-external-profile`, numbered
ADR-034 at the time). That PR went stale: the `034` number was taken by
ADR-034 "colocated module tests", and its regression test lived in the
now-removed `tests_suite` gitlink. This ADR supersedes that numbering; the fix
was rebuilt on top of `19.0` with the test colocated in
`connect_freeswitch/tests/`.
