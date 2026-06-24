# ADR-023: Normalize inbound DID `+`-format in dialplan regex and lookup

## Status
Accepted

## Context

Inbound DID routing matched calls by rendering a FreeSWITCH dialplan regex
from the **canonical** stored `connect.number.phone_number`. The core field
(`connect/models/number.py`) is a free-form `Char` with no normalization, so
admins store DIDs as `+41215121140`, `41215121140`, `0041…`, etc. — while a
trunk delivers `destination_number` in whatever format it chooses.

`connect_freeswitch.controllers.freeswitch_xml._route_inbound` looked the
number up by exact `phone_number`, then retried with a `+` **prepended**
(one direction only). On a hit it called
`connect.number.generate_dialplan`, which rendered
`dialplan_inbound_did` with `phone_number = re.escape(self.phone_number)`,
emitting:

```xml
<extension name="did_+41215121140">
  <condition field="destination_number" expression="^\+41215121140$">
```

So with a stored DID `+41215121140` and peoplefone sending
`destination_number=41215121140`, the **lookup** succeeded (via the
`+`-prepend) but the rendered regex `^\+41215121140$` did **not** match the
FreeSWITCH-side `41215121140`, and the call fell through to the 404
`unmatched_inbound` extension. REISO worked around it by storing all DIDs
without `+`; the reverse trunk format then breaks the same way, and the
lookup never even handled stored-without-`+` / incoming-with-`+`.

## Decision

Make both the regex and the record lookup tolerant of an optional leading
`+`, sourced from the trusted stored number:

1. **Regex (Option B).** `generate_dialplan` strips a single leading `+`
   from `phone_number`, `re.escape`s the bare digits, and renders
   `expression="^\+?<digits>$"` via a new `number_regex` template variable.
   This deterministically matches **both** `41215121140` and `+41215121140`.
   The extension name uses a clean `did_label` (digits, no `+`); the raw
   `phone_number` is still passed for any out-of-tree custom template.

2. **Symmetric lookup.** The asymmetric inline search is replaced by
   `connect.number._find_by_did(destination)` on the FreeSWITCH `_inherit`
   (next to `generate_dialplan`): exact match first, then the toggled-`+`
   form, in either direction; empty/falsy destination returns an empty
   recordset. The controller becomes a one-liner.

## Alternatives considered

- **Option A — anchor the regex on the live incoming `destination_number`.**
  Rejected. FreeSWITCH caches dialplan XML (mod_xml_curl), so emitting a
  different regex per call makes the routing table non-deterministic: a
  cached response from a `+`-form call would 404 a later no-`+` call,
  re-creating the bug. It also pipes an untrusted, possibly spoofed
  `destination_number` straight into the regex we emit. The issue suggested
  "A + B together," but once B makes `+` optional, A adds no coverage (any
  format difference beyond `+` fails `_find_by_did` before the template is
  ever reached) and only adds risk.

- **Normalize `phone_number` at write-time (store canonical E.164).**
  Rejected for this fix — a broader change requiring data migration of
  existing DIDs and a normalization policy across all trunk formats. The
  optional-`+` regex solves the reported correctness bug without touching
  stored data. Full number normalization remains a possible future change.

## Cross-branch backport

Per `CLAUDE.md` versioning rules, the same fix ports to the `18.0` branch
with the aligned tail version: `connect_freeswitch` moves
`19.0.1.10.0 → 19.0.1.10.1` and `18.0.1.10.0 → 18.0.1.10.1`. No schema
change, so no migration script is required. The backport ships as a
separate PR.
