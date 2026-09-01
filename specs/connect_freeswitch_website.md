# connect_freeswitch_website — Website Widgets for Working Schedules

## Module Info

- **Name:** Oduist Connect FreeSWITCH Website
- **Technical:** `connect_freeswitch_website`
- **Version:** 19.0.1.0.0
- **Depends:** `connect_freeswitch`, `website`
- **Application:** False
- **Auto-install:** False (explicit opt-in: it adds public endpoints)
- **License:** Proprietary

## Overview

Website snippets showing the working-schedule state of FreeSWITCH phone
numbers to site visitors (issue #57, ADR-037). The module is the only place
in the product with a `website` dependency: core `connect` owns the schedule
engine, `connect_freeswitch` owns the routing, this module only renders.

Two snippets (group "content" in the website builder):

- **Phone Status** (`s_connect_phone_status`) — inline status for footers:
  phone number, 🟢/🔴 indicator and an optional "(available until 16:00)" /
  "(opens tomorrow 08:00)" suffix. Options: phone number, show time,
  `tel:` link on the number, web page linked from the indicator.
- **Phone Opening Hours** (`s_connect_phone_opening_hours`) — table of the
  effective opening hours for the next N days for contact pages. Options:
  phone number, days ahead (1–60), show holiday/special-day labels, long or
  short date format.

## Models (`models/number.py`)

`_inherit = 'connect.freeswitch.number'` — adds
`name = fields.Char(related='phone_number')`. The website builder record
picker (`BuilderMany2One`/SelectMany2X) always reads the `name` field of
the model it browses, but the number model uses `phone_number` as
`_rec_name` and has no `name` column; the related field mirrors it so the
snippet options "Phone Number" picker works. No new models are defined.

`security/access_rules.xml` grants `website.group_website_designer`
read on `connect.freeswitch.number` and `connect.schedule` so the builder's
record picker can search numbers.

## Controllers (`controllers/main.py`)

Public, read-only, JSON responses; only numbers with `schedule_enabled` and
a schedule are exposed — anything else is a uniform 404. Rendering data is
read via sudo; dates and times are localized server-side (babel patterns via
`format_date`/`format_time`) in the website visitor's language
(`website=True` routes).

| Route | Purpose |
|---|---|
| `GET /freeswitch/schedule/status/<number_id>` | `{available, phone_number, status_text}` where `status_text` is a localized "available until …" / "opens at … / tomorrow … / <weekday> …" string built from `connect.schedule.get_status()` |
| `GET /freeswitch/schedule/opening_hours/<number_id>?days=N` | `{phone_number, days: [{date_short, date_long, hours, label, closed}]}` from `connect.schedule.get_day_data()`; `days` clamped to 1–60, default 10 |

## Frontend

- `static/src/snippets/` — public `Interaction`s
  (`public.interactions` registry, `web.assets_frontend`): fetch the JSON
  endpoint on start, replace the snippet placeholder with the rendered
  status line / hours table, restore the placeholder on cleanup. Snippet
  parameters are read from `data-*` attributes
  (`data-number-id`, `data-show-time`, `data-link-phone`, `data-link-page`,
  `data-days`, `data-show-labels`, `data-date-format`).
- `static/src/website_builder/` — builder options
  (`website-plugins` registry, `website.website_builder_assets` bundle):
  one plugin exposing two `BaseOptionComponent`s and the
  `connectPhoneNumber` builder action that stores the picked
  `connect.freeswitch.number` id into `data-number-id`.

## Tests

`tests/test_controllers.py` (HttpCase): available/unavailable status,
404 for numbers without a schedule and unknown ids, the `days`
clamping, all-closed calendars and holiday labels in opening hours.
