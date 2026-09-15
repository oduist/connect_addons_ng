# 062 — The Twilio softphone owns its own recent-calls list

## Problem

The softphone redesign asks the Recent tab to group calls by day ("Today",
"Yesterday", then a date) and to fold direction, outcome and duration into one
line per call.

The Recent tab was the shared `connect.calls` component, which lives in core
`connect` and is rendered by **every** provider's phone — Twilio, Telnyx,
Infobip, Vonage and LiveKit. It renders a flat, ungrouped table with a
different row shape and its own inline call-detail panel.

So the grouping could not be added without deciding who pays for it.

## Options considered

1. **Change the shared component in core.** One implementation, no
   duplication. But the markup and styling are what change, and they would
   change for four other providers' phones at the same time — phones that
   still use the older chrome the new rows are not designed for, and that
   nobody is testing in this pass. A visual change to core is a change to four
   products.

2. **Parameterise the shared component** (a `grouped` prop, a row-template
   slot). Keeps one copy, but the two renderings share almost no markup: the
   grouped list has day headers, a search box, a different row, and no inline
   detail panel. The parameters would not abstract a shared idea, they would
   just carry an `if` through core on behalf of one provider.

3. **Give `connect_twilio` its own `Recents` component.** A duplicated view;
   core and the other four providers are untouched.

## Decision

Option 3. `connect_twilio/static/src/components/phone/recents/` is the Twilio
module's own list, and the Twilio phone no longer imports
`@connect/components/calls/calls`.

This is the same trade ADR-031 already makes for the PBX-configuration models:
a duplicated copy in exchange for providers that can move independently. The
duplication is small (~190 lines of presentation logic) and it is *view* code,
which is exactly the category ADR-031 expects to diverge per provider — a
FreeSWITCH phone and a Twilio phone have no reason to render the same list.

Core `connect.calls` stays exactly as it was and remains the list every other
provider's phone renders.

## Consequences

- Core `connect` is untouched by the softphone redesign. No other provider's
  phone changes appearance.
- A fix to the *presentation* of recent calls now has two homes if it applies
  to both lists. A fix to the *data* — `get_widget_calls`, `connect.call`,
  `connect.favorite` — still has one, because `Recents` calls the same core
  methods rather than reimplementing them.
- When a second provider adopts this design, copy the component into that
  provider rather than hoisting it back into core. Hoisting is only correct
  once *every* provider wants the same list, at which point core
  `connect.calls` should be replaced outright instead of parameterised.

## Note on ordering

`Recents` asks `get_widget_calls` for `create_date desc, id desc` rather than
the method's `id desc` default. The list is cut into day groups from
`create_date`, so that has to be the sort key too; ordering by id is only a
proxy for it and drifts apart whenever rows are backfilled.
