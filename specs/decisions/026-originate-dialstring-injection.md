# ADR-026: Harden FreeSWITCH originate dialstrings against injection

## Status
Accepted

## Context

The project audit flagged two paths that interpolate semi-trusted input
into a FreeSWITCH `originate` dialstring via `str.format`/`%`:

- **`connect.call.originate_call`** (`models/call.py`): the dialled
  `number` came straight from the caller after only
  `re.sub(r'[\s()\-]', '', number)` (strip spaces/parens/hyphens). It is
  then interpolated into the channel-variable block
  (`odoo_destination_number={number}`) and the bridge data. A Connect
  User could pass `}`, `&`, `,`, `'`, `[`, `]` and append arbitrary
  channel variables or a second application — a toll-fraud / command
  vector.
- **`connect.freeswitch.parking.slot._action_unpark`**
  (`models/fs_parking_slot.py`): `parked_caller_number` /
  `parked_caller_name` come from the parking webhook (the inbound
  caller's SIP caller-id) and were interpolated into the originate
  command with only `'` stripped from the name. An attacker controlling
  the caller-id could inject originate metacharacters (stored injection).

A FreeSWITCH originate dialstring uses `{}`, `[]`, `<>`, `,`, `&`, `|`,
`'`, `"` as structural metacharacters, so any of these reaching the
string from user input is dangerous.

## Decision

Constrain the data at the point it enters the dialstring:

- **Dialled numbers** (`originate_call`): validate the post-strip value
  against `^\+?[0-9*#]{1,20}$` (optional leading `+`, then digits and the
  DTMF feature-code characters `*`/`#`). Anything else raises
  `UserError` — callers dial numbers, not dialplans.
- **Caller-id from webhooks** (parking unpark): the number keeps only
  `[0-9+*#]`; the display name drops the metacharacter set
  `{}[]<>,&|'"\` entirely. This sanitizes rather than rejects, because
  the value is machine-fed and a retrieval must not hard-fail on an
  odd caller-id.

Validation/sanitization lives at the use site (where the dialstring is
built), so every future originate path is forced to opt into the same
rule explicitly.

## Consequences

- Internal extensions and E.164 DIDs (with or without `+`) keep working;
  feature codes using `*`/`#` keep working.
- A genuinely exotic dialled value (letters, `;`, etc.) is now rejected
  with a clear error instead of being silently passed to FreeSWITCH.
- The 20-character cap on dialled numbers is generous for E.164 (max 15)
  while bounding abuse.
