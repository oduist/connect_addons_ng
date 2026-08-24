# Working Schedules

Working schedules route inbound calls differently during and outside of
business hours (FreeSWITCH numbers, `connect` ≥ 19.0.4.1.0 and
`connect_freeswitch` ≥ 19.0.2.1.0). A schedule combines three layers,
checked in this order for every inbound call:

1. **Special Working Days** — irregular hours for specific dates. They
   *always* win: if a date has special working days, they fully define
   that day's hours (they can also *extend* hours, e.g. open a Saturday).
2. **Public Holidays** — closures from the working calendar's global
   time off. Optionally play a voice message to callers.
3. **Working Schedule** — the weekly hours of a standard Odoo working
   calendar (`resource.calendar`), including its timezone.

## Setting up

### 1. Working calendar

Go to **Connect → Configuration → Working Times** and create a calendar
with the weekly hours (e.g. Mon–Fri 08:00–12:00, 13:00–17:00). Make sure
the **timezone** of the calendar is correct — all schedule math happens
in that timezone.

### 2. Working schedule

Go to **Connect → Configuration → Working Schedules** and create a
schedule pointing at the calendar. On the schedule form you manage:

- **Special Working Days** — name, date, work from/to. Several
  non-overlapping windows on the same date are allowed (e.g.
  08:00–12:00 and 13:00–16:00); overlapping windows for the same
  schedule are rejected. To fully close a date use a public holiday
  instead — special days always describe *working* windows.
- **Public Holidays** — the calendar's global time off entries. The
  optional **Prompt Message** is played to callers when a call arrives
  during that holiday.
- **Preview** — the computed opening hours for the next 14 days.

Schedules are reusable: any number of phone numbers can point at the
same schedule.

### 3. Phone number

On **Connect → FreeSWITCH → Numbers**, open a DID and enable **Use
Working Schedule**. The regular destination fields become the route
during working hours; the **After-hours Routing** group (user, callflow
or queue) takes over outside of them. **Prompt Language** selects the
piper TTS voice used for holiday prompt messages.

If no after-hours destination is configured, callers outside working
hours hear the holiday prompt (when set) and the call is hung up.

!!! note "Customized dialplan templates"
    The holiday prompt is rendered by the `dialplan_inbound_did`
    template. If you customized that template, reset it to the new
    default (or merge the `schedule_prompt` block) to get the prompt.

## Availability calendar

**Connect → Availability** shows the materialized schedule of all
working schedules in a calendar view: computed *Available* windows,
all-day *Closed* markers and the raw *Working Schedule* / *Public
Holiday* / *Special Working Day* layers (toggle them with the search
filters). Slots are regenerated automatically — daily by cron and on
every schedule/holiday/special-day change — over a rolling horizon of 60
days (`connect.schedule_slot_horizon_days` system parameter).

## Website widgets

Install **`connect_freeswitch_website`** (requires the Odoo `website`
module) to show opening information to site visitors. Two building
blocks appear in the website editor:

- **Phone Status** — for footers: the phone number with a 🟢/🔴
  indicator and an optional "(available until 16:00)" / "(opens
  tomorrow 08:00)" suffix. Options: phone number, show time, `tel:`
  link, a page linked from the indicator.
- **Phone Opening Hours** — for contact pages: the effective opening
  hours for the next N days, including holiday and special-day labels.
  Options: phone number, days ahead, show labels, long/short date
  format.

Only numbers with **Use Working Schedule** enabled can be selected; the
underlying public JSON endpoints (`/freeswitch/schedule/status/<id>`,
`/freeswitch/schedule/opening_hours/<id>`) expose nothing else. Dates
and times are localized in the website visitor's language.
