# ADR-024: Honour the `odoo_call_direction` channel variable in CDR parsing

## Status
Accepted

## Context

Calls launched via `fs_cli -x "originate ..."` (or any path that does not go
through the normal Verto/Sofia user flow) landed in Odoo as `connect.call`
records with `direction=incoming`, even though the call left the system
**outbound**. Reported as issue #43 (severity High, data quality), reproduced
during REISO outbound testing.

The CDR webhook handler
(`connect_freeswitch/controllers/freeswitch_cdr.py::_parse_cdr_xml`) derived
direction **only** from the FreeSWITCH-level `<channel_data><direction>`
field, defaulting to `inbound`:

```python
channel_data = root.find('./channel_data')
if channel_data is not None:
    direction = self._xml_text(channel_data, 'direction', 'inbound')
else:
    direction = 'inbound'
```

For `originate`-synthesised legs that FS-level field is unreliable, so the leg
was parsed as `inbound`. Downstream the chain is:

1. `connect_freeswitch/models/call.py::on_freeswitch_cdr` maps
   `direction == 'outbound'` → `technical_direction='outbound-api'`, else
   `'inbound'`.
2. `connect/models/call.py::_determine_direction` maps
   `technical_direction='inbound'` **without** a `caller_pbx_user` →
   `direction='incoming'`.

So a synthesised outbound leg (no caller `connect.user`) ended up as
`incoming`.

The dialplan already carries the authoritative answer: every routed leg is
tagged with an `odoo_call_direction` channel variable — `inbound` on the
inbound-DID extension and `outgoing` on the outgoing-route extension
(`connect_freeswitch/data/fs_templates.xml`). `mod_xml_cdr` emits that
variable inside `<variables>`, but the parser never read it.

## Decision

In `_parse_cdr_xml`, read the `odoo_call_direction` channel variable from
`<variables>` and let it **override** the `<channel_data>` inference when
present; fall back to the existing `<channel_data><direction>` logic when the
variable is absent (e.g. internal extension-to-extension calls that do not tag
a direction):

```python
odoo_call_direction = self._xml_text(variables, 'odoo_call_direction')
if odoo_call_direction == 'outgoing':
    direction = 'outbound'
elif odoo_call_direction == 'inbound':
    direction = 'inbound'
```

The dialplan vocabulary (`outgoing`/`inbound`) is mapped onto the
`outbound`/`inbound` vocabulary that `on_freeswitch_cdr` already understands,
so no change is needed in `on_freeswitch_cdr` or core `_determine_direction` —
the existing `outbound → outbound-api → outgoing` chain produces the correct
result.

This is backward-compatible with every existing flow:

| Flow | `odoo_call_direction` | Before | After |
|------|----------------------|--------|-------|
| UA-originated outbound (Verto → PSTN) | `outgoing` | `outgoing` (via caller_pbx_user) | `outgoing` (via outbound-api) |
| Inbound DID (PSTN → DID) | `inbound` | `incoming` | `incoming` |
| **`originate`-launched outbound** | `outgoing` | **`incoming`** | **`outgoing`** |
| Internal ext ↔ ext | absent | unchanged (fallback) | unchanged (fallback) |

## Alternatives considered

- **Infer direction from the channel name / leg role instead of the channel
  variable.** Rejected. The leg role (A/B, originator/originatee) is already
  derived heuristically for parent linking and is exactly what is unreliable
  for synthesised calls; the dialplan variable is an explicit, deterministic
  signal that costs nothing to read.

- **Map `odoo_call_direction` to `technical_direction` in
  `on_freeswitch_cdr` rather than to `direction` in the parser.** Functionally
  equivalent, but keeping the FS-specific vocabulary translation inside the
  parser keeps `on_freeswitch_cdr` working off a single normalized `direction`
  key and leaves the existing mapping untouched.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same fix ports to the `18.0` branch with
the aligned tail version: `connect_freeswitch` moves `19.0.1.10.1 →
19.0.1.10.2` and `18.0.1.10.1 → 18.0.1.10.2`. No schema change, so no
migration script is required. No files under `connect_freeswitch/deploy/`
change, so no Docker image rebuild is required. The backport ships as a
separate PR.
