# ADR-022: Preserve orphan call's caller/called/partner on bridge-pair merge

**Status:** Accepted
**Date:** 2026-05-25
**Builds on:** ADR introducing `reconcile_bridge_link` (commit b0c7094)

## Context

`reconcile_bridge_link` (introduced earlier) handles the bridge-pair
CDR race: when two `mod_xml_cdr` webhooks for sibling SIP legs hit
different Odoo workers concurrently, each worker's REPEATABLE READ
snapshot misses the other's just-created channel and mints its own
`connect.call`. A post-commit reconcile then runs `_merge_calls` to
fold the orphan channel onto the parent's call and unlink the
orphaned (now-empty) call row.

That fixed "two duplicate `connect.call` rows persist." But it left
two adjacent bugs that manifest as **`connect.call.called` empty
after a real bridge**:

1. **`_merge_calls` discards the orphan's fields.** It only moves
   `child.call = parent.call.id` and unlinks `old_call`. If the
   orphan happened to be the leg whose `called_number` is the
   user-facing digit (e.g. A-leg verto dialing `123`) and the
   surviving call was minted from the B-leg whose
   `caller_profile/destination_number` is an opaque token
   (`agent_5501ks91…@…`, `u:<verto-uuid>`), the digit value is gone.

2. **`process_call_event` had no backfill** for the
   no-race / sequential case. When B-leg arrived first, it created
   the call with `called=''` (computed from the opaque token);
   when A-leg arrived second as the secondary leg, `channel.call`
   got assigned but nothing copied A-leg's `called_number` onto the
   call. (The same is true mirror-wise for caller.)

Both observed in production traffic on `19.0-elevenlabs`:

| connect.call.id | A-leg `called` | B-leg `called` | survivor.called | survivor expected |
|---|---|---|---|---|
| 98 (verto/123 → EL agent) | `123` | `agent_5501ks91…` | `''` | `123` |
| 100 (verto/100 → user/100) | `100` | `u:fd1b4b30-…` | `''` | `100` |

(Call 98 hit the race path — A-leg's call became orphan, dropped on
merge. Call 100 hit the no-race path — backfill simply didn't
exist.)

## Decision

Backfill empty caller/called/partner from the data-bearing sibling,
in both code paths where the data can be lost.

### 1. `connect.models.call.Call.process_call_event` — sibling backfill

After assigning the secondary leg's `channel.call`, copy any empty
`call.caller` / `call.called` from the channel's now-resolved numbers:

```python
if not channel.call.caller and channel.caller_number:
    channel.call.caller = channel.caller_number
if not channel.call.called and channel.called_number:
    channel.call.called = channel.called_number
```

Runs unconditionally on every leg's `process_call_event` — cheap, and
the `not …` guard makes it a no-op when already populated. Covers the
no-race path.

### 2. `connect.models.channel.Channel._merge_calls` — orphan field rescue

Before `old_call.unlink()`, copy any non-empty `caller`, `called`,
`partner` from `old_call` into `parent.call` where `parent.call`'s
slot is empty:

```python
backfill = {}
if not parent.call.called and old_call.called:
    backfill['called'] = old_call.called
if not parent.call.caller and old_call.caller:
    backfill['caller'] = old_call.caller
if not parent.call.partner and old_call.partner:
    backfill['partner'] = old_call.partner.id
if backfill:
    parent.call.write(backfill)
```

Covers the race path: whichever of the two calls is destined to die
in the merge donates its useful fields to the survivor first.

## Options considered

**Option A (chosen): backfill in both places.** Minimal, defensive,
no schema change. Each guard is `not field` so it never overwrites
existing data. Idempotent.

**Option B: pick a deterministic "winner" call before merge** (e.g.,
always keep the call with the digit-only `called`, or always keep the
A-leg's call). Requires teaching `_merge_calls` how to identify the
"better" call; A-leg/B-leg distinction is fuzzy across providers
(it's not encoded as a flag). Punted.

**Option C: advisory-lock per bridge-pair to eliminate the race.**
Already rejected in the prior race-fix ADR — `reconcile_bridge_link`
is simpler and the post-commit fresh snapshot is sufficient. Doesn't
address the no-race backfill case (#1 above) anyway.

**Option D: teach `_get_channel_numbers` to recognise the verto
`u:<uuid>` form so the A-leg's `called_number` for call 100 resolves
to the dialed extension.** Cosmetic only — the sibling B-leg already
carries the digit form, and backfill picks it up. Skipping.

## Consequences

- `connect.call.called` (and `caller`) now reflect the dialed digit
  even when the surviving CDR is the opaque-token leg, in both the
  race and no-race paths.
- `_merge_calls` becomes data-preserving rather than data-destroying.
- No behavioural change for non-bridged calls or calls where the
  surviving leg already carries the right values (the `not field`
  guards short-circuit).
- ElevenLabs flows (which always have a B-leg with
  `called=agent_<uid>@…`) get a populated `called` reliably; the
  EL conversation lookup at `connect_elevenlabs/models/call.py:53-54`
  (`('caller', '=', self.caller), ('called', '=', self.called)`)
  now actually matches across calls instead of comparing empty
  strings.
