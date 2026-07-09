# ADR-034: Always serve the sofia `external` profile, even with no gateways

## Status
Accepted

## Context

The `external` sofia profile is served on demand from Odoo via `mod_xml_curl`
(`controllers/freeswitch_xml.py::_get_sofia_config`) — the static
`autoload_configs/sofia.conf.xml` ships an empty `<profiles/>`. SIP endpoints
register against `external` and modules bridge outbound legs via
`sofia/external/sip:…`, so the profile must exist independently of whether any
outbound **gateway** (SIP trunk) records exist.

`_get_sofia_config` gated the whole response on gateways:

```python
if not gateways:
    return self._not_found()
```

On a fresh env with no gateway records, Odoo answered the `sofia.conf` xml_curl
request with `<result status="not found"/>`. FreeSWITCH got **no** sofia
configuration at all, so the `external` profile could not start
(`sofia status` → `0 profiles`, `sofia profile external start` →
`Failure starting external`). No SIP registration was possible; only the Verto
(WebRTC) profile, which is served separately, kept working. This surfaced on a
fresh deployment (ODU-45).

The gate was a code regression on `19.0`: the sibling `19.0-twilio-fs-compat`
branch already rendered the profile unconditionally. The template
(`data/fs_templates.xml::config_sofia`) always renders the full
`<profile name="external">` and injects `{{ gateways_xml }}` (empty when there
are none), so the gate was the only thing suppressing a valid config.

## Decision

Drop the `if not gateways: return self._not_found()` gate. `_get_sofia_config`
now **always** renders the `external` profile; gateways are joined into the
profile only when present (empty string otherwise). A fresh env therefore serves
a valid `sofia.conf` and the `external` profile starts and accepts
registrations without any gateway, DID, or firewall record.

This does **not** revert ADR-028: the post-commit deferral of
`_reload_sofia_profile()` / `_reload_acl()` is still required so that a
newly-created gateway is committed (and thus visible to the separate xml_curl
cursor) before FreeSWITCH re-fetches the profile. ADR-034 only removes the
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

## Cross-branch backport

Per `CLAUDE.md` versioning rules the same one-line fix ports to `18.0` with the
aligned tail version. `18.0` may already carry the fix (like
`19.0-twilio-fs-compat`) — verify before porting. No schema change, so no
migration script is required. Regression coverage lives in
`tests_suite/connect_freeswitch/tests/test_sofia_config.py`.
