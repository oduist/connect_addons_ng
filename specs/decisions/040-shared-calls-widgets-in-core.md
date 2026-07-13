# ADR-040: Shared Calls Widgets in Core

## Status
Accepted

## Context
Two provider-agnostic phone-widget pieces were copy-pasted into each telephony
provider module, differing only in the `connect_<provider>.*` OWL template
namespace and the systray registry keys:

1. The **active-calls systray widget** (`ConnectActiveCallsTray` +
   `ConnectActiveCallsPopup`, the `fa-server` "Toggle Calls" icon) — duplicated
   in connect_twilio, connect_telnyx, connect_infobip.
2. The **Calls history tab** (`Calls` / `CallDetail`, `calls.js`) mounted inside
   the provider phone panel — duplicated in connect_twilio, connect_telnyx,
   connect_infobip and connect_asterisk.

Because each copy registered its systray item under a provider-unique key, Odoo
never deduplicated them: installing several providers (a supported
co-installation, per ADR-031) produced several identical "Toggle Calls" icons in
the systray. Both widgets are fully provider-agnostic — they only read the shared
core ledger (`connect.call.get_widget_calls`, `connect.favorite`) and never touch
any provider WebRTC SDK.

## Decision
Move both widgets into core `connect` as a single shared copy, and delete the
per-provider copies.

- `connect/static/src/services/active_calls/` — the active-calls systray widget,
  registered **once** via the `connect_active_calls` service. Registration is
  gated on `connect.group_user` membership (`await user.hasGroup(...)`), so only
  Connect users see it. Templates renamed to `connect.active_calls_tray` /
  `connect.active_calls_popup`.
- `connect/static/src/components/calls/` — the Calls history tab, templates
  renamed to `connect.calls` / `connect.call_detail`, exporting `Calls`. Each
  provider phone panel imports it (`import {Calls} from
  "@connect/components/calls/calls"`) and mounts it as a child, passing its own
  `bus` prop; the `busPhoneMakeCall` click-to-call contract is unchanged.
- Provider `__manifest__.py` files drop the `services/active_calls/*` asset glob;
  core adds `components/calls/*` and `services/active_calls/*` to
  `web.assets_backend`.

The provider-specific WebRTC dialer (its own systray icon + `Phone` main
component, one per SDK: Twilio Voice, Telnyx WebRTC, Infobip RTC, JsSIP, Verto)
stays in each provider module and is **out of scope** — those cannot be merged.
Deduplicating the dialer icons themselves (gating each on the user's
`originate_provider`) is deferred to a future change.

This applies only to JS/XML/SCSS assets and `__manifest__.py`; no Python source
changes, so the byte-identical-Python cross-series invariant is unaffected.
Because assets may legitimately differ between series branches, the 18.0 backport
is a separate manual port rather than a byte-identical cherry-pick.

## Consequences
- Exactly one "Toggle Calls" systray icon regardless of how many providers are
  installed; one source of truth for the Calls history tab (~2.5k lines of
  duplicated JS/XML/SCSS removed).
- The active-calls widget now also appears for asterisk / freeswitch / bird /
  connect-only installs (it did not before). This is acceptable and arguably an
  improvement — it reads the shared ledger and is now gated on `connect.group_user`
  (previously it was ungated and visible to every internal user).
- The "deliberately duplicated code (no mixins)" note in AGENTS.md continues to
  apply to the **Python** copies (exten dst-reference, caller-ID, BCP-47) — it did
  not cover these JS assets, which are now shared.
