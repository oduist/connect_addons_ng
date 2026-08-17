# ADR-055: Make softphone recording states visually explicit

**Status:** Accepted
**Date:** 2026-08-17

## Context

The Twilio and FreeSWITCH web phones use a filled circle for the idle recording
control. A filled circle is also a common recording-in-progress indicator, so
users can read an available manual action as confirmation that the call is
already being recorded. The generic active styling does not make the runtime
state sufficiently distinct.

The per-user **Record Calls** option enables automatic recording. Runtime
recording control is intentionally independent: a user can still start a
manual recording when automatic recording is disabled.

## Decision

Use the same explicit state language in both web phones:

- idle/off: a purple circular badge with a white dot and `REC` label meaning
  **Start Recording**;
- active/on: a purple `fa-stop-circle` meaning
  **Stop Recording**;
- transitions and errors keep their spinner and warning icons;
- expose the current state through a dynamic accessible label and
  `aria-pressed`.

The control remains visible when **Record Calls** is disabled. Its neutral idle
state means that no recording is active; clicking it starts a manual recording.
Once a manual or automatic recording is actually active, the control switches
to the purple stop state.

## Consequences

- An available recording action is no longer confused with an active
  recording.
- Twilio and FreeSWITCH use the same recording-control semantics.
- Disabling automatic recording does not remove the ability to record a
  specific call manually.
