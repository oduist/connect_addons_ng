# ADR-037: Working Schedule for inbound calls (core engine + FreeSWITCH v1)

## Problem

Issue #57 asks for working schedules on inbound phone numbers: route to
one destination during working hours and to another outside of them,
honor public holidays (optionally playing a voice message), allow
"special working days" that override both the weekly schedule and the
holidays (including *extending* hours), give admins a calendar overview
of computed availability, and let website visitors see a number's
current open/closed state and its opening hours.

Constraints coming from the existing architecture:

- Inbound routing is decided per call in Python for every provider
  (FreeSWITCH: mod_xml_curl → `/freeswitch/xml` →
  `connect.freeswitch.number.generate_dialplan()`), so a time-based
  branch can be evaluated at call time — no static artifacts to rebuild.
- Per ADR-031 the PBX config models are provider-owned, but a working
  schedule is not PBX technology: it is pure business-hours math, like
  OpenAI transcription it belongs in core.
- No module in the repo depends on `resource` or `website` yet; there
  are no `<calendar>` views and no website-facing code at all. Core and
  provider modules must not gain a `website` dependency.
- The issue text attaches the feature to "extensions" in one section and
  to "numbers" in another; inbound calls from the PSTN arrive on
  numbers (DIDs), and the issue's "Handling Inbound Calls" logic is
  written for the number.

## Decisions

1. **Schedule engine lives in core `connect`, on top of
   `resource.calendar`.** `connect` gains a `resource` dependency and a
   new `connect.schedule` model: `name`, required `calendar_id`
   (`resource.calendar` — weekly hours and timezone), M2M
   `special_day_ids`. Public holidays are the calendar's global leaves
   (`resource.calendar.leaves` with no resource), extended in core with
   an optional `prompt_message` text played to callers during that
   leave. Evaluation is provider-agnostic; provider modules only consume
   it.

2. **v1 provider integration: FreeSWITCH only, attached to the
   number.** `connect.freeswitch.number` gets `schedule_enabled`
   ("Use Working Schedule"), `schedule_id`, and an "unavailable"
   destination triple (`closed_destination` selection + `closed_user` /
   `closed_callflow` / `closed_fs_fifo_id`) mirroring the existing
   destination fields, which act as the "available" route.
   `generate_dialplan()` consults `schedule_id.get_status()` per call
   and picks the transfer target. Other providers can adopt the same
   pattern later; Asterisk is out of scope (inbound routing happens in
   the customer's PBX, not in Odoo).

3. **Evaluation order (from the issue), implemented in
   `connect.schedule.get_status(at_dt)`:** special working days for the
   date fully define that date's hours when present (several
   non-overlapping windows are allowed, so hours can be extended or
   split); otherwise an overlapping global leave means closed with its
   `prompt_message`; otherwise the weekly calendar attendances decide.
   All math is done in the calendar's timezone. The method returns
   availability plus `source`, `label`, `prompt_message`, `until` (end
   of the current state) and `next_open` — the latter two feed the
   website widgets. A sibling `get_day_windows(date_start, days)`
   returns per-day effective windows for previews, the availability
   calendar and the opening-hours widget.

4. **Special working days are shared records attached to schedules,
   not to numbers.** `connect.schedule.special_day` (`name`, `date`,
   `work_from`/`work_to` floats, M2M `schedule_ids`) keeps the issue's
   "assign one special day to many lines" workflow while staying
   provider-agnostic (numbers are provider-owned models, so a direct
   M2M from a core model to them is impossible). Overlapping special-day
   windows on the same date are rejected per schedule via a constraint.
   A special day always has `work_from < work_to`; fully closing a date
   is expressed with a (public holiday) leave, not a degenerate special
   day.

5. **The availability calendar is a materialized slot table.** Odoo
   calendar views render records, not computed functions, so a cron
   materializes `connect.schedule.slot` rows over a rolling horizon
   (default 60 days, `connect.schedule_slot_horizon_days` system
   parameter): effective `available` windows, raw `schedule` attendance
   windows, `holiday` and `special` layers, and an all-day `closed`
   marker for fully closed days. Slots regenerate for the affected
   schedules on any write to schedules, special days or leaves. The
   calendar view (first in the repo) colors by layer and filters by
   schedule, layer and availability — all three schedule types are
   visible in one view as the issue asks.

6. **Website widgets live in a new `connect_freeswitch_website`
   module** (`depends: [connect_freeswitch, website]`, not
   auto-installed) so neither core nor the provider gains a `website`
   dependency. Two snippets: *Phone Current Status* (🟢/🔴 with
   "available until …" / "opens …", optional page link and `tel:` link)
   and *Phone Opening Hours* (N days ahead, long/short dates, optional
   holiday/special-day labels). Both render client-side from public
   JSON endpoints (`/freeswitch/schedule/status/<number_id>`,
   `/freeswitch/schedule/opening_hours/<number_id>`) because website
   pages are cached while availability changes over time. The endpoints
   are read-only, expose only numbers with `schedule_enabled` (404
   otherwise) and format dates/times server-side in the website
   visitor's language.

7. **Access:** `connect.schedule`, `connect.schedule.special_day`,
   `connect.schedule.slot` — Connect User read-only, Connect Admin full
   CRUD; webhook group gets read on schedule/special day (routing runs
   under sudo anyway). Core also grants Connect Admin CRUD / Connect
   User read on `resource.calendar`, its attendances and leaves so PBX
   admins can manage working time without HR roles. Menus: a
   user-visible **Availability** calendar under the Connect root and an
   admin-only **Working Schedules** entry under Configuration.

8. **Holiday prompt is spoken by piper TTS in the DID dialplan.** The
   `dialplan_inbound_did` Jinja2 template gains an optional
   `answer`/`sleep`/`speak piper|lang|prompt` block before the
   transfer, following the IVR templates. The prompt language is a
   per-number selection reusing the FreeSWITCH piper language list
   (ADR-018). Customized templates keep working and simply skip the
   prompt until re-synced with the new default.

## Consequences

- Adding a provider later costs only: schedule fields on its number
  model, a branch in its render/route method, and a prompt playback in
  its native markup (Say for Twilio/Telnyx TwiML/TeXML) — the engine,
  calendar view and constraints are already in core.
- `connect` now installs the `resource` module. It is a lightweight
  base module shipped with every Odoo edition.
- The slot table trades storage for a native calendar UX; slot data is
  derived and regenerable at any time, so it needs no migrations and no
  backup guarantees.
- The website widgets are the first public browser-facing surface in
  the product; they expose only open/closed times of numbers explicitly
  configured with a schedule, never PBX internals.
- The 18.0 backport follows the standard cross-branch rules (same
  product version tail, per-series migration folders not needed — new
  tables only).
