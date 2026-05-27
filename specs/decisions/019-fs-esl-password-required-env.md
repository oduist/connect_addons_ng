# ADR-019: FreeSWITCH ESL password becomes a required per-installation env var

**Status:** Accepted
**Date:** 2026-05-27

## Context

`mod_event_socket` is the root-equivalent control plane of FreeSWITCH:
anyone who can authenticate against the ESL socket can run any FS API
command, originate calls, read configuration, and observe live events.
In this repository the ESL listener is bound to `127.0.0.1:8021` (see
`connect_freeswitch/deploy/freeswitch/conf/autoload_configs/event_socket.conf.xml`),
so exposure is normally limited to other containers on the host —
specifically the firewall service from ADR-014, which connects to ESL
to receive `sofia::*` events and apply `ipset` rules.

Until now the ESL password was hardcoded to the literal string
`ConnectNGESLPassword`:

- baked into `event_socket.conf.xml`,
- baked into `connect-firewall-service/config.py` as the pydantic
  default,
- mirrored in `deploy/README.md`, `deploy/firewall/oduflow-preset.yaml`
  and `docs/admin/firewall.md`.

The entrypoint already supported `FS_ESL_PASSWORD` as a `sed`
override, but only as a no-op if the variable was unset. Operators
who never bothered to set it ran with a password that has been in
this public repository and in the published `oduist/freeswitch`
image for the entire project history. Anyone who can reach
`127.0.0.1:8021` inside the FS container — for example via a sidecar
or a misconfigured `network_mode: host` neighbour — gains full FS
control.

A related cleanup: `vars.xml` carried
`<X-PRE-PROCESS cmd="set" data="default_password=CHANGE_ME"/>`. This
is a leftover from vanilla FreeSWITCH where sample SIP users
`1000-1019` reference `${default_password}`. In this repo those demo
users are stripped: `directory/default.xml` is empty (users come from
Odoo via `mod_xml_curl`, see `controllers/freeswitch_xml.py`),
`sofia.conf.xml` is empty (`<profiles/>`), and a repo-wide search for
`${default_password}` returns zero references.

## Options

1. **Fail-fast required env var.** Remove every hardcoded default;
   both FreeSWITCH and the firewall service refuse to start if
   `FS_ESL_PASSWORD` is unset. The operator generates one secret per
   installation and passes the same value to both containers.
2. **Random password generated on first FreeSWITCH start, persisted
   to a shared volume.** The firewall service mounts the same volume
   and reads the password at boot. Zero operator action.
3. **Manage the ESL password from the Odoo UI, push to FreeSWITCH on
   startup via a webhook.** Symmetrical with `firewall_service_token`.

## Decision

**Option 1.** The ESL password is now a required environment variable
on both containers, with no default and no fallback.

Why not Option 2: the shared-volume coupling presumes the two
containers always sit on the same host with the same volume mount.
That is the current reality (`network_mode: host` forces co-location)
but architecturally fragile, and it shifts the failure mode from a
visible "container won't start, fix your env" to an invisible
"firewall service reads the wrong file path and silently retries
ESL auth forever".

Why not Option 3: Odoo never talks to the ESL socket itself (only
the firewall service does), so adding an Odoo settings field would
create a duplicate source of truth without removing the need to set
the same value in container env vars. It is decorative complexity
for an operator who already has to deploy two containers.

The breaking change is intentional. Any deployment still relying on
the committed `ConnectNGESLPassword` is by definition vulnerable;
making it fail loudly is correct.

### How the substitution works

`event_socket.conf.xml` now ships with the obviously-broken
placeholder `__SET_FS_ESL_PASSWORD__`. `docker-entrypoint.sh::apply_esl_password()`
runs before `freeswitch` is exec'd and:

- exits 1 if `FS_ESL_PASSWORD` is empty;
- exits 1 if it contains an XML metacharacter (`<>"&`);
- exits 1 if the config file is missing or has no `name="password"` param;
- `sed`-substitutes the placeholder with the real value;
- exits 1 as a sanity check if the placeholder still survives the
  substitution.

We keep the `sed` approach (instead of e.g. an `X-PRE-PROCESS env-set`
in `vars.xml`) because it is already deployed and tested, the
operator can `cat` the file inside the container to verify the live
value, and there is no risk of edge cases in FreeSWITCH's XML
preprocessor on `<param value=>` attributes.

On the firewall service side, `fs_esl_password` loses its pydantic
default and becomes a required field — pydantic raises at
`ServiceSettings()` construction time if the env var is unset, which
happens during `__main__.run()` before any background task starts.

### Why a placeholder, not an empty string

If the entrypoint script crashes for any reason before reaching
`apply_esl_password()`, FreeSWITCH will still find a placeholder
that nothing can match against ("password mismatch" on every
connection) rather than a legitimate password it could accept.
Defence in depth.

### `default_password=CHANGE_ME` removed from `vars.xml`

Unused (zero callers in the repo), inherited from vanilla FreeSWITCH
demo users that this project does not ship. Keeping it would
suggest there is a meaningful password to configure when there is
not — readers would either set it to a real value and wonder why
nothing changed, or leave it as `CHANGE_ME` and wonder if they have
forgotten a security step. Both are noise.

## Consequences

- **Breaking change for any deployment that did not already set
  `FS_ESL_PASSWORD`.** Both containers refuse to start with a clear
  error message in stderr (FS: "FS_ESL_PASSWORD is not set. Generate
  a per-installation secret ..."; firewall: pydantic
  `ValidationError`). The operator picks a value
  (`openssl rand -hex 32`) and sets it on both.
- **FreeSWITCH image bumped to `oduist/freeswitch:1.10.0`** (manifest
  `19.0.1.10.0`). Existing `oduist/freeswitch:latest` users will pick
  the new image on next `docker pull`.
- **Firewall service image bumped to
  `oduist/freeswitch-firewall:1.1.2`.** `oduflow-preset.yaml`,
  `deploy/firewall/README.md`, and `docs/admin/firewall.md` updated
  to reference the new tag.
- **Cross-branch port.** Per the `Cross-branch versioning rules` in
  `CLAUDE.md`, `18.0` must receive the same change with manifest
  `18.0.1.10.0`. Tracked as a follow-up after this PR merges.
- **No Odoo data migration is required.** ESL is a container-to-container
  concern; nothing on the Odoo side changes shape.

## References

- ADR-014 — original firewall service design (defines the ESL coupling
  this ADR hardens).
- `connect_freeswitch/deploy/freeswitch/conf/autoload_configs/event_socket.conf.xml`
- `connect_freeswitch/deploy/freeswitch/conf/vars.xml`
- `connect_freeswitch/deploy/docker-entrypoint.sh` (`apply_esl_password`)
- `connect_freeswitch/deploy/firewall/src/connect_firewall_service/config.py`
- `docs/admin/firewall.md` (operator-facing guidance)
