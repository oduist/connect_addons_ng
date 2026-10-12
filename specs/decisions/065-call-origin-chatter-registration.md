# 065 — Log calls to the click-to-call origin and its contact

## Problem

A click-to-call from a lead (or any other record) logged the call and its AI
summary only on `connect.call.partner`. Provider `originate_call()`
implementations receive `res_model`/`res_id` but keep only a partner derived
from them, so the record the user actually worked on never saw the call.
Bridge modules (`connect_crm`, `connect_sale`, `connect_helpdesk`,
`connect_account`, `connect_project`, `connect_hr`) each posted the summary to
their own linked record from a separate `summary` constrains, so one record
reachable by two paths would get it twice, and the call log line itself
reached only the partner.

## Options

1. **Pass the origin through every provider** — each `originate_call()` writes
   `res_model`/`res_id` on the channel it creates. Nine provider copies, and
   providers that create the channel later from webhooks or a sidecar
   (Asterisk, 3CX, FreeSWITCH) cannot carry it at all.
2. **Change the click-to-call RPC** — the phone widgets call a new core method
   that records the origin and then dispatches. Seven widget copies per series,
   and every server-side caller of `originate_call()` would bypass it.
3. **Wrap the composed `originate_call()` in core** — `connect.settings`
   patches the final class method in `_register_hook()`, the technique
   `base_automation` uses, so every provider records the origin first.

## Decision

**Option 3**, plus a pending-origin hand-off and a single registration path.

- The wrapper stores `{model, res_id, number digits, at}` on the calling
  `connect.user` (`originate_origin`, written with SQL to skip `write()`
  side effects). `process_call_event()` lets an outgoing call claim it when the
  last nine digits of `called` match within ten minutes, independent of when
  and how the provider creates the channel.
- `connect.call._get_registration_targets()` returns the origin and the call's
  partner; bridge modules append their linked record instead of posting
  themselves. `_get_registration_records()` adds each target's contact
  (`partner_id`/`partner` many2one to `res.partner`) and removes duplicates.
  `register_call()` (call log) and `register_call_summary()` (summary, still
  gated by **Register Summary**) post to exactly that list.
- Transcripts under eight words are not summarized: the model only answers
  "too short to summarize", which would otherwise be posted everywhere.

## Consequences

- Bridge records now also receive the call log line, not only the summary.
- The origin is best effort: a click-to-call followed by a manual call to the
  same number within ten minutes before the first call reaches Odoo would claim
  it. Calls started without a record (softphone dial pad) keep the old
  partner-only behavior.
- Removed methods: `register_partner_call_summary()` (core) and the six bridge
  `register_*_call_summary()` constrains.
