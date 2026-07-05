# ADR-029: Play ringback to the caller during FreeSWITCH bridges

## Status
Accepted

## Context

Issue #113: on FreeSWITCH, an inbound caller heard **silence** instead of a
ringing tone while the destination phone was ringing, and again after a
callflow IVR gathered input and bridged to a user. Twilio has no such
problem because `<Dial>` plays ringback natively.

FreeSWITCH only generates ringback audio for the caller when the channel
variables `ringback` (pre-answer bridges) or `transfer_ringback`
(post-answer bridges) are set before `bridge`. None of the module's
dialplan templates set them, so every `bridge` produced dead air:

| Flow | Channel state at bridge | Needed |
|---|---|---|
| DID → user (`dialplan_user_bridge`) | not answered | `ringback` |
| DID → ring group (`dialplan_ring_group`) | not answered | `ringback` |
| DID → IVR → user (`dialplan_ivr`, `dialplan_ivr_choice`) | **answered** | `transfer_ringback` |
| digit-only fallback (`freeswitch_xml._route_internal`) | not answered | `ringback` |

The stock `us-ring` tone that `${us-ring}` usually resolves to is **not**
available: the image wipes FreeSWITCH's default configs (`Dockerfile`
`rm -rf .../etc/freeswitch/*`) and the module ships a minimal `vars.xml`
that never defined it, so `${us-ring}` would expand to an empty string.

## Decision

1. Define the ring tone once as a global in the deployed
   `freeswitch/conf/vars.xml`:
   `us-ring = %(2000,4000,440,480)` (the FreeSWITCH-standard US ring
   cadence: 2 s on / 4 s off, 440+480 Hz). One global keeps the cadence
   in a single place an admin can change.
2. Before **every** `bridge` in the dialplan templates
   (`dialplan_user_bridge`, `dialplan_ring_group`, `dialplan_ivr`,
   `dialplan_ivr_choice`) and in the `_route_internal` digit-only
   fallback, set **both**:
   ```xml
   <action application="set" data="ringback=${us-ring}"/>
   <action application="set" data="transfer_ringback=${us-ring}"/>
   ```
   Setting both is deliberate: FreeSWITCH applies `ringback` only when the
   caller channel is unanswered and `transfer_ringback` only when it is
   already answered, and it ignores the non-applicable one. Setting both
   removes any dependence on knowing the exact answer state of a given
   flow, so no bridge path can regress to silence.

## Consequences

- Callers now hear a ring cadence on inbound DID → user, DID → ring
  group and DID → IVR → user, matching the Twilio behaviour.
- `${us-ring}` is a FreeSWITCH global expanded at runtime; it passes
  through the Jinja template renderer untouched (`${…}` is not Jinja
  syntax).
- Deploy change: `vars.xml` gains the `us-ring` global, so the
  `oduist/freeswitch` image must be rebuilt for the tone to resolve on a
  fresh container. The template changes ship as module data and take
  effect on module upgrade; on an old image `${us-ring}` is empty
  (degrades to today's silence, no regression).
- The cadence is US-style. A deployment wanting a local cadence (e.g.
  Swiss `%(1000,4000,425)`) changes the single `us-ring` global.
