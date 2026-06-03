# ADR-022: Endpoint `auth_password` auto-generated as a typeable passphrase

## Status
Accepted

## Context

GitHub issue [#81](https://github.com/oduist/connect_addons_ng/issues/81).

`connect.endpoint.auth_password` (added by `connect_freeswitch`,
`models/endpoint.py`) was a plain free-text `Char` with no generation,
no validation and no minimum length. A user could save a single
character as the SIP credential — a real security risk, since this
password authenticates a device registering to FreeSWITCH.

The credential is special in that operators frequently **type it by
hand** into a desk phone or a softphone on a mobile device with no
copy/paste. A random alphanumeric string is secure but painful to enter;
a passphrase is both.

Prior art in the codebase:
- `connect_freeswitch/models/fs_user.py` — `webrtc_password`,
  `readonly=True`, generated with `secrets.token_urlsafe(16)`.
- `connect_twilio/models/user.py` — `generate_twilio_password()`.

## Decision

1. **Generate a human-readable passphrase.**
   `connect_freeswitch/models/passphrase.py` ships a curated wordlist
   (~240 short, neutral words) and `generate_passphrase(word_count=5)`,
   which returns five `word+digit` groups joined by hyphens, e.g.
   `flour3-tower9-rome1-watching2-hello8`. It uses `secrets` (CSPRNG),
   never `random`. Entropy ≈ `5·log2(240) + 5·log2(10) ≈ 56 bits`.

2. **Auto-manage the field.** `auth_password` becomes
   `readonly=True, copy=False` with
   `default=lambda self: generate_passphrase()`, so every new endpoint
   (including inline rows on the user form and duplicated records) gets a
   fresh strong password the user cannot accidentally weaken.
   `action_regenerate_auth_password()` is the explicit, server-side way
   to rotate it.

3. **Reveal/Copy UI.** A small read-only OWL field widget
   (`static/src/widgets/endpoint_password/`, registered as
   `endpoint_password`) masks the value by default, adds a Show/Hide eye
   toggle (for manual entry on devices without paste) and a
   Copy-to-clipboard button. The inline endpoint list on the user form
   keeps `password="True"` masking.

4. **Non-destructive backfill.** `backfill_endpoint_passwords(env)` in
   `connect_freeswitch/__init__.py`, called from
   `migrations/19.0.1.10.0/post-migrate.py`, fills only endpoints whose
   `auth_password` is empty. Existing passwords — even weak manual ones —
   are left untouched, per the issue's acceptance criteria.

## Alternatives considered

- **Random alphanumeric (`secrets.token_urlsafe`) like
  `webrtc_password`.** Rejected for this field: WebRTC passwords are
  copy/pasted by the browser client; endpoint passwords are frequently
  typed by hand into SIP hardware, where a passphrase is far easier.
- **Keep the field editable, only add a default.** Rejected — the issue
  requires the value be auto-managed so it cannot be silently weakened.
- **Odoo's built-in `CopyClipboardChar` widget.** Rejected — it renders
  the value in plaintext and offers no Show/Hide; it cannot satisfy
  "masked by default, revealable on demand".
- **Force-rotate weak existing passwords during migration.** Rejected —
  the acceptance criteria mandate a non-destructive migration; rotating a
  password an operator already programmed into a live device would break
  that device's registration on upgrade.

## Related security hardening

Storing a strong password is pointless if every user can read it. Two
row/menu-level fixes ship in the same change:

1. **Endpoints are private to their owner.** `connect.endpoint` had an
   `ir.model.access` granting `group_user` read but **no record rule**,
   so any Connect user could list every endpoint — and now every SIP
   password. Added `rule_connect_endpoint_user`
   (`[('connect_user_id.user', '=', user.id)]`) and the paired
   `rule_connect_endpoint_admin` (`[(1, '=', 1)]`) in core
   `connect/security/record_rules.xml`, mirroring the existing
   `connect.user` / `connect.call` rules. Rules live in **core** because
   the model and `connect_user_id` are core; `group_admin` implies
   `group_user`, so the admin rule is required for admins to keep full
   visibility. The FreeSWITCH directory/dialplan controllers read
   endpoints via `sudo()`, so XML generation is unaffected.

2. **Firewall is admin-only.** `group_user` previously had read access to
   `connect.firewall.{whitelist,blacklist,event,agent}`. Those four
   `*_user` `ir.model.access` records were removed (Odoo drops the stale
   rows on upgrade) and `menu_firewall_root` is gated on
   `connect.group_admin`. Firewall is an infrastructure concern with no
   end-user use case.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, port to the `18.0` branch with the
aligned tail versions `18.0.1.10.0` (`connect_freeswitch`) and
`18.0.3.1.5` (`connect`), reusing the same `generate_passphrase()` /
`backfill_endpoint_passwords()` helpers and the same security rules, with
the per-series entry point `migrations/18.0.1.10.0/post-migrate.py`.
Ships as a separate PR after this one merges.

## Consequences

- New endpoints always carry a strong, typeable SIP password.
- Operators can reveal, copy or regenerate the password from the form.
- Pre-existing endpoints with empty passwords are healed on upgrade;
  those with a set password are unchanged.
- The field is no longer freely editable; rotation goes through
  **Regenerate**.
