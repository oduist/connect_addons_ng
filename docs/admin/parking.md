# Call Parking Setup

Call parking is provided by FreeSWITCH's `mod_valet_parking`. It works
out of the box after upgrading the `connect_freeswitch` module to
`19.0.1.7.0` or later — no manual FreeSWITCH configuration is needed.

## What's wired up automatically

- **`mod_valet_parking` module** is loaded at FreeSWITCH start
  (`autoload_configs/modules.conf.xml`).
- **Presence / BLF support** is enabled on the sofia profile:
  `manage-presence=true`, `send-presence-on-register=first-register`,
  `presence-hosts=<fs_domain>,<local_ip>`. These are emitted by the
  `fs_template_config_sofia` Jinja2 template, so an upgrade of the
  module is enough to pick them up.
- **Parking dialplan** is served dynamically by the Odoo `mod_xml_curl`
  handler. When a SIP phone dials a parking slot extension, Odoo
  renders the `dialplan_valet_parking` template on the fly and returns
  it. This means you never need to restart FreeSWITCH to add or remove
  slots.
- **Six default slots** (701–706) are created on first install from
  `data/parking_slots.xml` (`noupdate="1"` — changes survive module
  upgrades).

## Managing slots

Navigate to **FreeSWITCH → Parking Slots**. Admins can:

- Create new slots with any dialable extension.
- Rename, re-order (`sequence` field) or deactivate slots.
- Inspect the currently parked call directly on the slot form, with an
  **Unpark** button for debug.

Each slot extension must be **unique**. The frontend tab shows slots
in `sequence`, then `exten` order; keep the total count small (≤ 8)
so the grid fits without scrolling.

## BLF on hardware SIP phones

On a phone that supports BLF, programme one DSS button per slot with
the following SIP SUBSCRIBE target:

```
<slot-exten>@<fs_domain>
```

For example, for slot `701` on a FreeSWITCH whose `freeswitch_domain`
is `pbx.example.com`, the BLF URI is `701@pbx.example.com`. The lamp
turns on when the slot is occupied and off when empty. Pressing the
key dials the slot extension, which parks (if empty) or retrieves (if
occupied).

## Webhook endpoint

When a channel enters or leaves a slot, FreeSWITCH posts to Odoo:

- `GET /freeswitch/webhook/parking?event=entered&slot=<s>&uuid=<u>&caller_number=<n>&caller_name=<name>`
- `GET /freeswitch/webhook/parking?event=released&slot=<s>`

These are idempotent; replays are safe. The base URL is taken from
`web.base.url`, so ensure that system parameter is set to the
externally reachable Odoo URL — the same constraint that already
applies to call recording (ADR-005).

## Verifying the installation

Inside the FreeSWITCH container:

```bash
fs_cli -x "module_exists mod_valet_parking"      # → true
fs_cli -x "sofia status profile internal"        # PRESENCE-HOSTS present?
fs_cli -x "valet_info default"                   # list occupied slots
```

End-to-end test:

1. Open the Verto widget in a browser, originate a call to a second
   extension, answer it.
2. In the Parking tab click slot 701 — the slot card shows the caller's
   number. On a BLF-enabled SIP phone subscribed to `701@domain`, the
   lamp is now red.
3. Pick up the call from the SIP phone by pressing the DSS key, or
   click the occupied slot card in another browser session.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| BLF lamp never lights up | Phone not subscribed to `<slot>@<fs_domain>` or sofia profile missing presence params — reload profile and re-register the phone |
| Parked call card stays empty in the widget | Webhook URL unreachable from the FreeSWITCH container — check that `web.base.url` resolves from inside the FS container |
| "Slot is already occupied" when parking | Previous park did not get a `released` event; check FreeSWITCH logs and retrieve the slot manually via **Unpark** in the slot form |
| `connect.call` form shows no Park button | The call's `status` is already in an end state (`completed`/`failed`/…) or the slot is already linked |
