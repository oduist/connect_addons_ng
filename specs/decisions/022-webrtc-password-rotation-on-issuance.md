# ADR-022: Rotate the WebRTC/Verto password on every credential issuance

**Status:** Accepted
**Date:** 2026-06-02

## Context

Each `connect.user` with WebRTC enabled has a `webrtc_password`
(`connect_freeswitch/models/fs_user.py`) used to authenticate the Verto
softphone against FreeSWITCH `mod_verto`. Until now that password was
generated **once** — via `secrets.token_urlsafe(16)` in `create()`/`write()`
when WebRTC is first enabled — and then reused indefinitely.

This was reported as issue #36: during the initial REISO deployment the
admin user's `webrtc_password` was set to a known plaintext value that leaked
into chat transcripts and possibly browser DevTools history. Because the
password never changes, a leaked value stays valid forever. The maintainer's
follow-up: *"We can do more — re-generate the Verto password on every
`user.login()` operation."*

Two mechanics make a cheap, effective fix possible:

- The softphone fetches its credentials from
  `connect.settings.get_webrtc_config`
  (`connect_freeswitch/models/settings.py`), called once per page load by
  `connect_freeswitch/static/src/js/phone_service.js`. A second, parallel
  JSON-RPC route `/connect/webrtc/config`
  (`connect_freeswitch/controllers/webrtc.py`) returns the same payload but is
  not used by the current JS.
- FreeSWITCH re-authenticates **every** Verto registration live against the DB
  value through the XML directory binding
  (`connect_freeswitch/controllers/freeswitch_xml.py`, route `/freeswitch/xml`,
  `auth='none'`). So changing the DB value takes effect immediately — **no FS
  reload, no `xml_locate` flush** is required.

## Options

1. **Override `res.users._login` / `authenticate`** to rotate once per Odoo
   authentication (the literal reading of "on every `user.login()`").
   Rejected: the `_login` signature drifted across Odoo 17/18/19
   (`login`/`password` → `credential` dict), it is a `classmethod` running in
   its own short-lived cursor (fragile side-effect writes), and it fires on
   *every* authentication including API/RPC/cron contexts where no softphone is
   involved.
2. **Rotate at credential issuance** inside `get_webrtc_config`, through a
   shared helper on `connect.user`. The freshly generated value is the one
   returned to the client and the one FS checks — zero desync. Version-stable
   (our own `@api.model` method, fixed signature). Rotates ~once per softphone
   boot. *Chosen.*
3. **One-time / single-use token model** (`webrtc_password_rotated_at`, nonce
   table). Rejected as over-engineered for the threat: FS needs a directory
   password it can compare, so cleartext-in-DB is inherent to `mod_verto` auth;
   a rotating cleartext value already shrinks the leak window to one page load.

## Decision

Adopt **option 2**: rotate the WebRTC password on every config issuance via a
shared helper `connect.user._rotate_webrtc_password()`
(`connect_freeswitch/models/fs_user.py`), and **synchronize the user's open
tabs over a private bus channel**.

### Helper API

```python
def _rotate_webrtc_password(self):
    """Generate, store and broadcast a fresh WebRTC/Verto password."""
```

- Generates `secrets.token_urlsafe(16)`, writes it with `sudo()`
  (`webrtc_password` is `readonly` and `group_user` has `perm_write=False` on
  `connect.user`; `get_webrtc_config` runs as the logged-in non-admin user),
  and returns the new value.
- Broadcasts `{login, password}` to the user's **private** bus target
  (`self.user.partner_id`) under the notification type
  `connect_freeswitch.verto_credentials`. The private target is essential —
  the shared `connect_actions` string channel is global and would leak the
  secret to other users.

### Affected paths

- `connect_freeswitch/models/fs_user.py`: defines `_rotate_webrtc_password`.
  The existing `create()`/`write()` "generate once if missing" logic is kept
  unchanged — it still seeds an initial password when WebRTC is first enabled
  (so the XML directory has a value even before the first softphone boot, e.g.
  for inbound user-bridge ringing). The helper is an unconditional overwrite.
- `connect_freeswitch/models/settings.py` (`get_webrtc_config`): rotates and
  returns the helper's value (not a re-read of the field, to avoid a stale
  record cache in the same recordset).
- `connect_freeswitch/controllers/webrtc.py` (`/connect/webrtc/config`, legacy
  duplicate route): same rotation, so the parallel path never hands out a
  stale, non-rotating password.
- `connect_freeswitch/static/src/js/verto_client.js`: new `updateCredentials({login, password})`
  setter — updates the in-memory login/password without forcing a re-register;
  the next reconnect/re-login uses the fresh password.
- `connect_freeswitch/static/src/js/phone_service.js`: subscribes to
  `connect_freeswitch.verto_credentials` and calls
  `vertoClient.updateCredentials(payload)`.

### Multi-tab synchronization (why the bus push)

Rotating on issuance means: tab A boots with password `P1`; opening tab B (or
reloading) rotates the DB to `P2` and registers with `P2`. Tab A still holds
`P1` in memory. FS does **not** re-challenge an already-established Verto
session, so tab A's active call survives — but tab A's next reconnect/
re-register would send the stale `P1` and fail until that tab is refreshed.

The bus push fixes this: when the password rotates, the server notifies the
user's other tabs over their private channel, and each live `VertoClient`
updates its stored password in place. Active calls are untouched; every tab of
the user converges on the current password, so any later reconnect succeeds.

## Consequences

- **A leaked WebRTC password self-invalidates** on the user's next softphone
  boot (next `get_webrtc_config`). No FS reload is needed.
- **Multi-tab is not a regression** — tabs are kept in sync via the private bus
  channel; active calls survive a rotation triggered by another tab.
- **No proactive migration.** Existing passwords are not bulk-rotated on
  upgrade; they roll over naturally on the next softphone boot. The one-off
  rotation of the leaked REISO PROD admin password is an operational task
  (the XML-RPC `write` in issue #36), not code.
- **No admin "rotate now" button** in this change.
- **No Docker rebuild.** Nothing under `connect_freeswitch/deploy/` changes;
  the directory binding already serves the live DB value.
- **Cross-branch.** The change ports verbatim to the `18.0` branch
  (`18.0.1.9.3 → 18.0.1.9.4`) as a separate backport branch per the repo
  conventions.
- **Cross-ref ADR-016** (Verto login format and the two issuance paths).

## Verification

1. Upgrade `connect_freeswitch` to `19.0.1.9.4`.
2. For a WebRTC-enabled user, read `webrtc_password` from the DB, then call
   `connect.settings.get_webrtc_config` as that user. The returned `password`
   differs from the prior DB value and equals the new DB value. Calling it
   twice yields two different passwords (rotation-per-issuance).
3. POST to `/freeswitch/xml` (`section=directory`, `action=sip_auth`,
   `user=<_get_verto_login()>`, `domain=<freeswitch_domain>`): the returned
   `<param name="password" value="…">` equals the just-issued password — the
   directory binding serves the rotated value with no FS reload.
4. Open the softphone in two browser tabs; load the second one. The first
   tab's softphone keeps working and its `VertoClient.password` is updated via
   the `connect_freeswitch.verto_credentials` bus event.
5. Establish a call, rotate the password, confirm the active call is not
   dropped (FS does not re-challenge mid-session), while a forced re-register
   with the old password is now rejected.

## References

- Issue #36 (Critical, operational): "rotate the WebRTC password on REISO PROD
  admin user" + maintainer comment "re-generate the Verto password on every
  `user.login()`".
- ADR-016 — Verto login format and the two credential-issuance paths.
- ADR-010 — autoanswer/WebRTC refactor context.
