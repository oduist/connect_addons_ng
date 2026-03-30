# 009 — FreeSWITCH Click-to-Call via Server-Side Originate

## Problem

Users need to click a phone number in an Odoo form and initiate a call through FreeSWITCH, matching the UX already available in `connect_twilio`.

## Options Considered

### A — Client-side Verto
Phone field shares the VertoClient from the systray component via an OWL service.
Rejected: only works for WebRTC users, doesn't ring SIP phones, requires sharing state between OWL component trees (broke the systray in a previous attempt).

### B — Server-side originate (chosen)
Phone field calls `connect.call.originate_call()` via ORM. Server sends FreeSWITCH `originate` command via XML-RPC. FS rings user's endpoints (a-leg), bridges to target number via gateway (b-leg).

### C — Hybrid with originate_type field
User chooses 'server' or 'client' mode. Overkill for now.

## Decision: Option B — Server-Side Originate

Server-side originate via `freeswitch_api('originate', ...)`:

- Works for all endpoint types (SIP, WebRTC, both)
- Rings multiple endpoints simultaneously
- Phone field widget is trivial — just an ORM call, identical to Twilio's pattern
- Systray component stays untouched

## Consequences

- Requires XML-RPC connectivity to FreeSWITCH (already configured for status checks)
- Requires at least one outgoing route + gateway for external calls
- Internal calls (to extensions) bridge directly without a gateway
