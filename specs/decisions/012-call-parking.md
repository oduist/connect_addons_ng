# ADR-012: Call Parking (Valet) with BLF and Verto Parking Tab

**Date:** 2026-04-21
**Status:** Accepted

## Problem

Operators need standard office-grade call parking that works consistently across hardware SIP phones and the browser Verto widget:

1. On a **hardware SIP phone** a parked slot should appear on a DSS (speed-dial) button, where the same extension dials to both park (when empty) and retrieve (when occupied), with a **BLF lamp** that reflects the slot's busy state.
2. In the **browser Verto widget** operators want a dedicated Parking tab alongside the dialer, with one card per slot showing the parked caller's name and number, and Park / Pick-up buttons.
3. From the `connect.call` form the current call should be parkable with one click into the first free slot.
4. The number of slots is small and admin-configurable (default 6, visually fitting into the widget).

## Options Considered

### Parking engine
- **A) `mod_valet_parking`** — built-in FreeSWITCH module that stores channels in a named lot with named slots, plus presence/BLF support.
- **B) `mod_fifo`** — queue semantics, not slot semantics; no BLF per position.
- **C) Custom uuid_park + in-memory map** — reinvents what valet_parking already does.

### Configuration model
- **A) Fixed extension range** (e.g. `701–799`) as a setting — trivial to wire up, but no place to hold per-slot state (who parked, caller name) and no way to rename or deactivate a single slot.
- **B) `connect.freeswitch.parking.slot` records** — one DB record per slot. CRUD via Odoo, holds live state, feeds the frontend directly via `search_read`.

### Retrieval / unpark
- **A) Originate to user's endpoints → dialplan extension** that runs `valet_park <lot> <slot>` — identical code path for DSS-retrieval and Pick-up click.
- **B) `uuid_bridge` between caller's active channel and the parked channel** — requires knowing the user's current channel UUID; tricky when user has no active call.

### Synchronising state with Odoo
- **A) Dialplan webhook** (`curl` on park entry, `api_hangup_hook` on exit) — push-based, near-zero latency, idempotent.
- **B) ESL subscription + background poll** — more moving parts, stateful, harder to operate.

## Chosen Approach

| Area | Choice |
|------|--------|
| Engine | `mod_valet_parking`, single lot `default` |
| Slots | Model `connect.freeswitch.parking.slot` (one record per slot) |
| BLF | `manage-presence=true` + `presence-hosts` on sofia profile; dialplan sets `presence_id=<slot>@<domain>` before `valet_park` |
| Park action | `uuid_transfer <remote-leg-uuid> 'valet_park default <slot>' inline` via XML-RPC `freeswitch_api` |
| Retrieve action | `originate <user-endpoints> <slot> XML default`; same dialplan extension handles DSS-button and Pick-up |
| State sync | Two webhooks (`entered` / `released`) on the same URL, idempotent; fired by dialplan `curl` and `api_hangup_hook` |
| Frontend bridge | Server emits `parking_state_changed` on bus channel `connect_actions`; the phone service forwards to the Verto widget's local EventBus |

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Slot model (not a range) | Per-slot state (`parked_call`, `parked_caller_*`) is a first-class field; admin can CRUD without restarting FreeSWITCH |
| `presence_id` set in dialplan (not directory) | Same channel can be parked in *any* slot; we can't hard-code the presence identity at register time. Setting `presence_id` right before `valet_park` publishes the correct SUBSCRIBE dialog |
| Park the remote leg, not the user's leg | Parking the far side preserves the operator's own channel for continued UI interaction (transfer announcement, hold music, etc.) |
| `action_fs_park_by_uuid(uuid)` on `connect.call` | The Verto widget only knows the Verto `callId` (FS UUID). The server maps UUID → channel → call → slot, so the frontend stays free of Odoo record IDs |
| Webhook GET with query params | Easier to emit from dialplan `curl`/`api_hangup_hook` than crafting a POST body. Idempotent on replay |
| Served dialplan (not static) | The valet extension is rendered from a Jinja2 template (ADR-007) with the slot's `exten` and webhook URL. Changing slots doesn't require a FreeSWITCH restart — `mod_xml_curl` re-fetches on next dial |
| Bus channel `connect_actions` reuse | Already consumed by `connect_twilio` for `connect_notify` / `reload_view`; adding another event type is the least-surprising path |

## Implementation Details

### Dialplan (rendered from template `dialplan_valet_parking`)
```xml
<extension name="connect_valet_parking_{{ slot }}">
  <condition field="destination_number" expression="^{{ slot }}$">
    <action application="answer"/>
    <action application="set" data="presence_id={{ slot }}@${domain_name}"/>
    <action application="set" data="api_hangup_hook=bgapi curl {{ webhook_url }}/freeswitch/webhook/parking?event=released&amp;slot={{ slot }}"/>
    <action application="curl" data="{{ webhook_url }}/freeswitch/webhook/parking?event=entered&amp;slot={{ slot }}&amp;uuid=${uuid}&amp;caller_number=${caller_id_number}&amp;caller_name=${caller_id_name} background"/>
    <action application="valet_park" data="{{ lot_name }} {{ slot }}"/>
  </condition>
</extension>
```

### Sofia profile presence params (appended to `fs_template_config_sofia`)
```xml
<param name="manage-presence" value="true"/>
<param name="send-presence-on-register" value="first-register"/>
<param name="presence-hosts" value="${fs_domain},${local_ip_v4}"/>
```

### XML controller routing (`freeswitch_xml.py::_route_internal`)
Before the regular extension lookup, match the destination against an active parking slot. If found, render the valet dialplan extension and return.

### Webhook idempotency
- `entered` with the same UUID twice → no-op (early return, fields not overwritten).
- `entered` for an unknown slot → logged warning, 200 response (FreeSWITCH has no way to recover from webhook errors; don't break the park).
- `released` on an already-empty slot → 200 no-op.

### Bus protocol
Channel: `connect_actions`
Event type: `parking_state_changed`
Payload: `{id, exten, is_occupied}`

Frontend (`phone_service.js`) subscribes via `bus_service.subscribe("parking_state_changed", …)` and re-emits the event on the local Verto EventBus as `parkingStateChanged`; the `ParkingPanel` component refreshes on that event.

## Files Changed

### Server
- `connect_freeswitch/models/fs_parking_slot.py` — new model + webhook handlers
- `connect_freeswitch/models/call.py` — `fs_parked_slot`, `action_fs_park`, `action_fs_park_by_uuid`
- `connect_freeswitch/controllers/freeswitch_parking.py` — `/freeswitch/webhook/parking` endpoint
- `connect_freeswitch/controllers/freeswitch_xml.py` — route parking extens to the new dialplan template
- `connect_freeswitch/data/fs_templates.xml` — new `dialplan_valet_parking` template; presence params in sofia template
- `connect_freeswitch/data/parking_slots.xml` — six default slots (701–706)
- `connect_freeswitch/views/fs_parking_slot_views.xml` — admin CRUD
- `connect_freeswitch/views/call_views.xml` — Park button + parked-slot badge
- `connect_freeswitch/security/access_rules.xml` — ACLs
- `connect_freeswitch/deploy/freeswitch/conf/autoload_configs/modules.conf.xml` — load `mod_valet_parking`
- `connect_freeswitch/__manifest__.py` — version bump `19.0.1.7.0`

### Frontend
- `connect_freeswitch/static/src/js/parking_panel.js` — `ParkingPanel` OWL component
- `connect_freeswitch/static/src/xml/parking_panel.xml` — template
- `connect_freeswitch/static/src/js/phone_panel.js` — tabs state (Dialer/Parking)
- `connect_freeswitch/static/src/xml/phone_systray.xml` — tab bar
- `connect_freeswitch/static/src/js/phone_service.js` — bus subscription
- `connect_freeswitch/static/src/css/phone_systray.css` — tab + slot styling

### Tests
- `tests_suite/connect_freeswitch/tests/test_parking.py` — park, unpark, webhook (incl. HTTP case)

### Docs
- `docs/user/parking.md`, `docs/admin/parking.md`, `docs/mkdocs.yml`
