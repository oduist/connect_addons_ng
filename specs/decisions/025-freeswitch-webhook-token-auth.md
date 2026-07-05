# ADR-025: Shared-token authentication for FreeSWITCH → Odoo HTTP endpoints

## Status
Accepted

## Context

A full-project security audit found that every HTTP endpoint FreeSWITCH
uses to talk to Odoo was completely unauthenticated (`auth='none'`, no
token, signature, or IP check):

1. `/freeswitch/xml` (mod_xml_curl gateway) — the worst case: the
   directory section response embeds **cleartext SIP endpoint passwords,
   WebRTC passwords and the mod_xml_rpc admin credentials**. Any host
   that could reach Odoo could dump every PBX credential
   (`POST /freeswitch/xml` with `section=directory`) and gain full
   FreeSWITCH control — a direct toll-fraud vector.
2. `/freeswitch/webhook/cdr` — anonymous callers could create fake
   `connect.call` records without limit.
3. `/freeswitch/webhook/recording/<filename>` — anonymous unbounded
   uploads stored base64 in the database (disk DoS, forged recordings).
4. `/freeswitch/webhook/parking` — anonymous parked-call state spoofing.

The same audit found the Twilio master `auth_token` field-granted to
`connect.group_webhook` — the identity all public webhook controllers
run under — making it readable through `connect.settings.get_param()`
from any webhook execution context.

The repository already contains the right pattern:
`firewall_api.py::_check_token` validates a Bearer token from an
admin-only settings field with `secrets.compare_digest`, fail-closed.

## Options considered

1. **IP allowlist.** Breaks behind reverse proxies and Docker NAT where
   the peer address is the proxy, and X-Forwarded-For is spoofable.
   Rejected.
2. **Per-endpoint tokens.** Four secrets to generate, store, mask and
   pair with the container — configuration sprawl with no security gain
   over one secret, since all four endpoints trust the same peer
   (the FreeSWITCH container). Rejected.
3. **One shared `freeswitch_webhook_token`** validated by a common
   helper, transported per channel capability. **Chosen.**

## Decision

A single shared secret, `connect.settings.freeswitch_webhook_token`
(admin-only `groups=`, masked `display_` companion via the existing
`PROTECTED_FIELDS` mechanism), authenticates every FreeSWITCH → Odoo
HTTP call. `controllers/token_auth.py::check_fs_webhook_auth()` accepts
the token from, in order:

- `Authorization: Basic` password part — mod_xml_curl
  (`gateway-credentials`/`auth-scheme` params) and mod_xml_cdr
  (`cred`/`auth-scheme` params);
- `Authorization: Bearer` — symmetry with the firewall API;
- a `token` query parameter — the dialplan `curl` application used by
  valet parking (Odoo renders these URLs itself and injects the token);
- a path segment — recording uploads, where `record_session` derives the
  file format from the URL extension, so a query string after `.wav`
  would break it. The recording route became
  `/freeswitch/webhook/recording/<token>/<filename>`.

Comparison uses `secrets.compare_digest`. **Fail-closed**: an empty
stored token rejects everything. The token is auto-generated
(`secrets.token_urlsafe(32)`) by the field default, `post_init_hook`,
and the `19.0.1.10.2` post-migration (`ensure_webhook_token`), so
existing installs lock the endpoints immediately on upgrade.

On the FreeSWITCH side the token arrives via the `FS_WEBHOOK_TOKEN` env
var (`vars.xml` `env-set` → `$${webhook_token}` in `xml_curl.conf.xml`
and `xml_cdr.conf.xml`). Recording and parking URLs need no container
config: Odoo embeds the token when rendering the dialplan.

The Twilio fix is independent and one line: drop `connect.group_webhook`
from `auth_token`'s `groups=`. Webhook signature validation reads the
token via `sudo()` and keeps working; all non-sudo readers are
admin-driven UI flows.

## Consequences

- **Operational (breaking, by design):** after upgrading
  `connect_freeswitch` to 19.0.1.10.2, Odoo answers 401 to FreeSWITCH
  until the container runs the matching image (≥ tag `1.10.2`) with
  `FS_WEBHOOK_TOKEN` set to the same value as the Odoo setting. The
  entrypoint logs a loud warning when the var is unset. A "soft"
  rollout was rejected: it would keep the credential-dumping endpoint
  open by default.
- The operator pairing flow mirrors the firewall token: generate a
  value, paste it into the Odoo settings field (masked to `****` after
  save) and into the container env.
- The token appears inside rendered dialplan XML (parking/recording
  URLs) and therefore in FreeSWITCH logs at debug level. Acceptable:
  that XML is only served to an already-authenticated FreeSWITCH and
  the exposure is equivalent to the container env var itself.
- Recording uploads additionally gained a 256 MB size cap (DoS guard).
