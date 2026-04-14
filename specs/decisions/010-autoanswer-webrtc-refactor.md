# 010 — Auto-Answer Headers + WebRTC/SIP Architecture Refactoring

## Problem

1. Click-to-call (ADR 009) requires the user to manually answer their own phone (a-leg) before the target number rings. SIP phones support auto-answer via vendor-specific SIP headers. Verto clients can auto-answer programmatically.

2. The current architecture puts both SIP and WebRTC config on `connect.endpoint`, but an Odoo user can only have one WebRTC phone (browser-based Verto client). SIP endpoints can exist independently of Odoo users (e.g., lobby phones, conference rooms).

## Decision

### WebRTC moves to `connect.user`, SIP stays on `connect.endpoint`

- `connect.user` gains `webrtc_enabled`, `originate_ring`, and auto-generated `webrtc_password`
- Verto login uses `res.users.login` (email) — no separate username needed
- `connect.endpoint` becomes purely SIP: `auth_user`, `auth_password`, `originate_ring`, `auto_answer_header`
- `sip_enabled` removed — all endpoints are SIP by definition
- `sip_ring` renamed to `originate_ring` — controls click-to-call participation only; incoming calls ring all endpoints

### Standalone SIP endpoints

- `connect.endpoint.connect_user_id` becomes optional
- Endpoints without a user get their own `exten` (extension number) for routing
- Endpoints with a user inherit the user's exten

### `username` moves to `connect_twilio`

- Core `connect.user` no longer has `username` — it was only used for Twilio SIP domain registration
- `connect.user.user` (res.users) becomes required
- `get_user_by_uri()` becomes a no-op in core; `connect_twilio` overrides it

### Auto-answer for click-to-call

- SIP: configurable `auto_answer_header` Selection field on endpoint (vendor-specific SIP headers like `Alert-Info`, `Call-Info`, `Answer-Mode`, etc.)
- Verto: `auto_answer=true` channel variable on the Verto leg; JS client checks and auto-answers

## Consequences

- FreeSWITCH directory XML must serve separate entries for SIP endpoints and WebRTC users
- `originate_call()` builds a-leg from user's SIP endpoints (filtered by `originate_ring`) + WebRTC (if enabled and `originate_ring`)
- Dial-string for incoming calls includes ALL active endpoints + WebRTC (not filtered by `originate_ring`)
- Standalone endpoints need their own extension to be reachable
- Migration script copies existing endpoint WebRTC settings to user level
