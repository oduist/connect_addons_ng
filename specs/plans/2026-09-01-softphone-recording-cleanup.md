# Softphone recording-control cleanup plan

> **For agentic workers:** steps use checkbox (`- [ ]`) syntax for tracking.
> Verify every line reference against the working tree before editing — this
> plan was written from an audit of the tree at commit `3823411`.

**Goal:** Remove the garbage left by the iterative REC-button work (PR #143
`a7ca1cb` → PR #191 `4b8db26`) on the Twilio and FreeSWITCH softphones, fix the
four functional defects the iterations left behind, and converge the
client↔server recording contract on one shape. No new features.

**Spec references:** `specs/connect_twilio.md` (Runtime softphone recording
control), `specs/connect_core.md` (connect.channel), `specs/connect_freeswitch.md`,
`specs/decisions/055-*.md`, `specs/decisions/056-recording-state-from-provider.md`.

## Background — what the audit found

Two PRs iterated on the same seam. Each iteration solved its bug but left the
previous attempt's scaffolding in place:

- #143 added the recording-control contract with a payload shape sized for both
  providers (`recording_path`, `supported`, `channel_sid`) — Twilio adopted
  only part of it, FreeSWITCH kept its state in ESL channel vars, so several
  keys/columns are write-only or never written.
- #191 moved recording truth to the provider (ADR-056) but reinstated the
  removed `record_calls` heuristic client-side in the same commit, and wired
  six new broadcasts into a `BroadcastChannel` handler that has been dead
  (bare `return`) since the initial import.
- Two i18n/CSS/props layers of the FreeSWITCH systray predate the tabs layout
  and are fully overridden.

## Global constraints

- Branch off `19.0`; run everything from the worktree.
- **Python stays byte-identical across series branches**; nothing here needs a
  `release.version_info` branch.
- **Manifest bumps at most once per module on this branch:**
  `connect` `19.0.4.3.0` → `19.0.4.4.0` (field removal ⇒ feature-level bump,
  carries the migration), `connect_twilio` `19.0.2.3.0` → `19.0.2.3.1`,
  `connect_freeswitch` `19.0.2.1.4` → `19.0.2.1.5`.
- Comments in English; delete the debugging narratives, don't translate them.
- Every behavior change lands with a test in the owning module's `tests/`;
  pure-JS changes are verified with the `agent-browser` skill (see AGENTS.md
  "Self-driven verification").
- Docs/specs/ADR updates land **in the same commit** as the code they follow.

---

## Part A — functional fixes (behavior changes)

### A1. Remove the client-side `record_calls` seeding (Twilio) — finishes ADR-056

**Problem.** `phone.js:60` (`this.recordCalls = !!props.token_data.record_calls`)
and `applyExpectedRecordingState()` (`phone.js:476-481`) seed the button to
*Stop Recording* at `accept` from the user flag — exactly the heuristic
ADR-056 removed server-side, one layer up. With callflow-not-recording + flag
on, a click during the poll window reproduces ADR-056's original failure
(`Could not stop recording`).

**Decision.** The client never guesses. On `accept` the button renders the
**busy spinner, disabled**, until the first `state` RPC response arrives (the
existing `syncRecordingState` poll, first answer ≈1.5 s); from then on it
tracks server state only.

- [ ] Delete `applyExpectedRecordingState()` and its call site(s); delete
      `this.recordCalls` (phone.js:60).
- [ ] Set the pre-settle presentation via the existing busy path (do not
      invent a new state value): mark `recordingBusy` on `accept`, clear it on
      the first applied result or when the poll gives up.
- [ ] Drop `record_calls` from `get_client_token()` token_data
      (`connect_twilio/models/user.py:777`) and from the prop plumbing
      (`main.js:18-22`) — `phone.js:60` was its only consumer. The server-side
      automatic-recording use of `connect.user.record_calls` is untouched.
- [ ] Keep the rollback path (`phone.js:548-551`) only if it still has a
      caller after the seeding is gone; otherwise delete it.
- [ ] Test: extend `connect_twilio/tests/test_recording_controls.py` —
      token payload no longer contains `record_calls`.
- [ ] Amend ADR-056 (see Part D) — this is a refinement of that decision, not
      a new ADR.

### A2. Retire the `'manual-off'` sentinel (Twilio)

**Problem.** `connect_twilio/models/channel.py:218` writes
`recording_control_ref = 'manual-off'` after a successful stop. Nothing reads
that value by name; because it is truthy it (a) makes the state RPC's
short-circuit (`:153`) skip asking Twilio for the rest of the call, and (b) a
stop clicked while it is set falls back to using the literal string as a
recording SID (`:211`).

**Decision.** A successful stop clears the ref:
`'recording_control_ref': False`. The state RPC then consults Twilio again
(correct: a genuinely stopped recording returns nothing → `off`), and the stop
fallback is only ever `Twilio.CURRENT`.

- [ ] Change the write at `connect_twilio/models/channel.py:218`.
- [ ] Test: stop, then call `state` again — assert the mock Twilio client *is*
      consulted and the result is `off` with an empty ref (regression for the
      short-circuit); assert a second stop uses `Twilio.CURRENT`, never a
      stale sentinel.

### A3. Recording errors must actually surface (Twilio)

**Problem.** `phone.js:606` reports recording failures through
`this.notify(...)`, which is a no-op: `notify` is gated on
`call_popup_is_enabled`, hard-coded `false` at `phone.js:136` and never set
anywhere else.

**Decision.** The recording toggle's error path uses the standard Odoo
notification service directly (`useService('notification')`), bypassing the
in-widget popup machinery. The dead `notify()`/`call_popup_is_enabled` pair is
**out of scope** (pre-existing, affects `setCallStatus` too) — flag it in the
commit message, do not rework it here.

- [ ] Replace the `notify` call in `_onClickRecordingToggle`'s error path with
      the notification service (type `danger`, the server's error text).
- [ ] Browser check: force a stop failure (mock/disconnect) and confirm the
      toast appears.

### A4. Stop the duration timer on remote hangup (FreeSWITCH)

**Problem.** When the far end hangs up, the bus pushes `callState: "idle"`;
`_syncRecordingForProps` (`phone_systray.js:143-157`) resets the recording
state (the #143-era code cleans up) but `durationInterval` keeps ticking for
the life of the panel (the older sibling doesn't).

**Decision.** The `idle` transition resets both.

- [ ] In the `props.callState !== "active"` branch, call
      `_stopDurationTimer()` and reset `state.callDuration`.
- [ ] Browser check: place a call, hang up from the far end, confirm the
      interval is cleared (no ticking `callDuration` in the component state).

---

## Part B — dead-code deletion (no behavior change intended)

Twilio widget (`connect_twilio/static/src/components/phone/phone/`):

- [ ] `phone.js` — delete the entire unreachable `bc.onmessage` body
      (`:247-375`, dead behind a bare `return` since the initial import,
      including ~15 commented `console.log`s). Keep the `BroadcastChannel`
      itself only if something still posts *and* a live handler remains after
      this deletion; otherwise remove the channel construction too.
- [ ] `phone.js` — delete `_broadcastRecordingState()` (`:450-460`) and all 9
      call sites; delete the `tbcRecordingState` remnants.
- [ ] `phone.js` — delete `state.recordingPath` (written `:123`, `:445`,
      `:960`; read nowhere).
- [ ] `phone.js` — delete the unused `dialTone` import (`:8`); its only use is
      the commented-out `:1271`.
- [ ] `phone.js:528` — align the stray `console.warn` with the file's
      `cwarn` helper.
- [ ] `phone.js:462-475` — remove the misplaced retry-rationale paragraph from
      above `applyExpectedRecordingState` (the accurate copy lives at
      `:483-489`); A1 deletes the function anyway — make sure the comment goes
      with it.
- [ ] `getRecordingIconClass()` (`:582`) — after A1/C3, simplify to the two
      reachable outcomes (busy handled earlier; `on` → stop icon); drop the
      orphaned `fa-dot-circle-o` idle branch (idle renders the `REC` span,
      `phone.xml:137-143`).

Twilio server (`connect_twilio/models/channel.py`):

- [ ] `:120-133` — replace the debugging-session narrative (which names a real
      recording SID from a customer account) with one sentence; the rule is
      already stated cleanly at `:16-20`.
- [ ] `:153` — drop the impossible `''` alternative
      (`if result['state'] in ('off', '')` → `== 'off'`); the payload
      guarantees a Selection value.

Core seam (`connect/models/channel.py`):

- [ ] Remove the `recording_control_path` field (`:51`) and its read
      (`:242`) — no provider ever writes it; Twilio's `recording_path` is
      permanently `''`, FreeSWITCH keeps its path in ESL vars. Ship
      `connect/migrations/19.0.4.4.0/post-migration.py` dropping the column
      (mirror the `19.0.2.0.1` FreeSWITCH `is_default` drop).
- [ ] Remove the `supported=` parameter and `supported` payload key
      (`:236-250`) — no caller passes it, no client reads it. Keep
      `_softphone_recording_unsupported()` as the dispatcher fallback (see C3).
- [ ] Remove the `channel_sid` echo from the payload (`:244`) — no client
      reads it.
- [ ] Update `connect/tests/test_recording_controls.py` assertions that pin
      the removed keys.

FreeSWITCH systray (`connect_freeswitch/static/src/`):

- [ ] `js/phone_systray.js:159-165` — remove the unreachable `!callId` branch
      of `syncRecordingState()`; its `_t("Call UUID unavailable")` string then
      leaves the `.pot`/`de/fr/it/ru.po` on the next export (do the export in
      this branch; don't hand-edit the po files beyond removing the entry).
- [ ] `js/phone_systray.js:288` + `phone_service.js:143` — drop the unread
      `displayMode` prop from `PhoneSystray` (it is real on `PhonePanel`,
      dead on the systray).
- [ ] `js/phone_panel.js:15` + `phone_service.js:148` — drop the unused
      `connect` prop.
- [ ] `js/phone_panel.js:48-50, 61, 69` — remove the `phoneClose` listener; no
      emitter exists (`closeDialpad()` is the live path).
- [ ] `js/phone_systray.js:144` — move the `callId` computation below the
      early return.
- [ ] `css/phone_systray.css:15-36` — delete the pre-tabs positioning blocks
      (`.o_phone_mode_dropdown .o_phone_dialpad`, `.o_phone_mode_float
      .o_phone_dialpad`); the tabs-era `.o_phone_panel_body .o_phone_dialpad`
      (`:267`) always wins.
- [ ] `css/phone_systray.css:39-46` — strip the overridden card chrome
      (border/box-shadow/width, duplicate padding) down to what actually
      survives.
- [ ] `css/phone_systray.css:176-184` + `xml/phone_systray.xml:144` — collapse
      the `o_phone_recording_btn_idle`/`_active` pair: transparent border
      moves to the base class, active keeps only its background/color delta.
      Align the class naming with Twilio's `.active` while touching it.

FreeSWITCH server (`connect_freeswitch/models/channel.py`):

- [ ] `:116-118` — stop fetching `odoo_recording_ref` for the payload (an ESL
      round-trip per response that no client reads); the stop path re-fetches
      it when it actually needs it.
- [ ] `:114` — `'supported': True` goes away with the core key.
- [ ] `:44` — drop the unreached `channel_sid` fallback from
      `_freeswitch_call_id` (see C2).
- [ ] `:103-106` — remove the redundant `env.user.connect_user.record_calls`
      gate from the state seed: `_freeswitch_has_default_recording(call_id)`
      already implies it (the dialplan only arms `record_session` under
      `{% if record_calls %}`), and the requesting user's flag is the wrong
      user for inbound legs. Keep the channel-var check as the single source.
- [ ] Test: extend `connect_freeswitch/tests/test_recording_controls.py` for
      the seed (recording armed + requester flag off → still seeds `on`).

---

## Part C — contract convergence (small API decisions)

### C1. One payload identifier key: `call_id`

Today: Twilio JS sends `channel_sid`, FreeSWITCH JS sends `call_id`, core
accepts `channel_sid|call_sid` (nobody sends `call_sid`), FreeSWITCH accepts
`call_id|channel_sid` (nobody sends `channel_sid` there).

- [ ] Both clients send `call_id`.
- [ ] Core `_softphone_recording_channel` (`connect/models/channel.py:261`)
      reads `call_id`, keeping `channel_sid` as a deprecated alias for one
      release (assets can be cached across an upgrade); delete the dead
      `call_sid` alias now.
- [ ] FreeSWITCH `_freeswitch_call_id` reads `call_id` only.
- [ ] Update both providers' recording tests to the canonical key (they
      already send per-provider keys; assert the alias still resolves in the
      core test).

### C2. `unsupported` becomes a real (tiny) contract

`_softphone_recording_unsupported()` stays as the dispatcher fallback for a
provider key with no implementation, but the clients finally handle it:

- [ ] Both `_applyRecordingResult` implementations: `state === 'unsupported'`
      hides the recording button (today it renders an enabled idle icon that
      does nothing useful).
- [ ] Keep `connect/tests/test_recording_controls.py`'s unsupported-path test;
      drop its `supported`-key assertions (Part B).

### C3. FreeSWITCH keeps its own guards — documented, not unified

`_freeswitch_check_access` re-implements the ownership policy over live ESL
channel vars instead of calling core `_check_softphone_recording_access`, and
never calls `_check_softphone_recording_active`. This is **deliberate** and
stays: FreeSWITCH state is authoritative in the switch (the `connect.channel`
row can lag or be absent mid-call), and a dead channel fails the `uuid_getvar`
probe anyway, which subsumes the liveness check.

- [ ] Add a short comment on `_freeswitch_check_access` stating the rationale
      and pointing at the core pair, in the ADR-031 deliberate-duplication
      spirit.
- [ ] No code change.

---

## Part D — documentation, spec and ADR sync (same commits as the code)

- [ ] **Amend `specs/decisions/056-recording-state-from-provider.md`** (add a
      dated "Amendment" section — same file, no new number):
      the live-status match is the three-value `TWILIO_LIVE_RECORDING_STATUSES`
      set, not `in-progress` alone; the client polls
      (`{attempts: 40, delay: 1500}` ≈ 60 s), it is not a single on-start
      lookup; and the client-side `record_calls` seeding that survived the
      original decision is now removed — the pre-settle presentation is the
      disabled spinner.
- [ ] `specs/connect_twilio.md` — Runtime softphone recording control section:
      remove seeding/`applyExpectedRecordingState`, describe the settle
      behavior, the `call_id` key, the cleared-ref stop semantics, the
      notification-service error path.
- [ ] `specs/connect_core.md` — `connect.channel`: drop
      `recording_control_path`; payload table loses `supported`/`channel_sid`,
      gains the `call_id` (+ deprecated `channel_sid` alias) resolver note;
      note the 19.0.4.4.0 migration.
- [ ] `specs/connect_freeswitch.md` — payload/seed changes (B), guard
      rationale (C3).
- [ ] `connect/docs/user/recordings.md` — the REC button paragraph: it shows a
      brief spinner after answering until the state is confirmed (replaces the
      "may briefly show the neutral state" wording).
- [ ] `docs/changelog.md` — 2026-09 entries: recording button no longer
      guesses (Twilio), recording errors now show a notification, FreeSWITCH
      panel timer fix.
- [ ] i18n export for `connect_freeswitch` after the dead-string removal.

---

## Explicitly out of scope

- The dead in-widget popup machinery (`notify`/`call_popup_is_enabled`,
  `setCallStatus` toasts) beyond the A3 bypass — separate decision.
- Pre-existing dead code in `phone.js` unrelated to recording (`lastTime`,
  `xPhoneInfoDisplay`, `state.isActive`, `_onClickTransfer`, commented-out
  Contacts tab, `.o_phone_lines_position`/`.o_suggestion` SCSS, missing
  `o_optional_dial_panel_position` rule) and the Telnyx commented-out buttons
  — worth a follow-up sweep, but mixing it in here hides the recording diff.
- `starting`/`stopping` written-then-overwritten inside one transaction
  (`connect_twilio/models/channel.py:164-167, 204-207`): observable only as
  chatter noise; removing the tracked selection values is a schema/UX call
  that isn't needed for this cleanup. Revisit if the chatter noise bothers
  anyone.
- Any change to automatic (dialplan/TwiML) recording behavior.

## Test / verification matrix

| Change | Verification |
|---|---|
| A1 seeding removal | `run_odoo_tests connect_twilio` (token payload), agent-browser: answer a callflow-recorded call → spinner → Stop; answer an unrecorded call → spinner → REC |
| A2 sentinel | new unit test (stop→state→stop sequence against the mock client) |
| A3 error toast | agent-browser with a forced stop failure |
| A4 timer | agent-browser remote hangup |
| B deletions | `run_odoo_tests connect connect_twilio connect_freeswitch` all green; grep proves each deleted symbol has zero remaining references |
| C1 key | core resolver test covers `call_id` + alias |
| C2 unsupported | existing unsupported test + button hidden in a forced-unsupported browser check |

## Suggested commit slicing

1. `[connect_twilio]` A1 + A2 + A3 (+ their spec/ADR/doc edits)
2. `[connect_freeswitch]` A4 + FreeSWITCH Part B (+ i18n export)
3. `[misc]` core payload/field cleanup (B core + C1 + C2) with the migration
4. `[connect_twilio]` widget dead-code deletion (B Twilio)
