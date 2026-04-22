# check-queue-extension — 2026-04-22

**Branch:** `19.0-connect-migrate`
**Goal:** Diagnose why an inbound PSTN call to a FreeSWITCH FIFO queue failed with `SUBSCRIBER_ABSENT`, then add a UI warning that makes the underlying misconfiguration (queue without a linked `connect.exten`) visible before it breaks calls.
**Related files:**
- `connect_freeswitch/models/fs_fifo.py`
- `connect_freeswitch/views/fs_fifo_views.xml`
- `connect_freeswitch/models/number.py` (root cause reference)

## Context

An inbound call from Twilio to DID `+37257237879` failed. The user asked to look at FreeSWITCH service logs via Oduflow. Root cause turned out to be an Odoo-side misconfiguration: `connect.number` (id=3) had `destination='fs_fifo'` pointing to `connect.fs_fifo(1)`, but that queue had no linked `connect.exten`, so `number.generate_dialplan` fell back to `str(fs_fifo.id) = '1'` as the transfer target, and the `default` context's generic `local_extension` rule tried to `bridge(user/1@...)` — a user that does not exist. After diagnosis we added a `is_exten_set` computed flag plus a red form alert and a danger-decorated list row so admins notice unlinked queues before routing breaks.

---

## Step 1. Inspect FreeSWITCH service logs

**Tool:** `mcp__oduflow_oduist__list_services`

**Arguments:**
```json
{}
```

**Result:**
```
Active Services:
- fs (oduflow-svc-fs): running
  Image: oduist/freeswitch:1.0.4
  Port: 48081
  URL: https://fs.team.dev.oduist.com
  Env: ODOO_URL=https://190-connect-migrate.team.dev.oduist.com, FS_DOMAIN=team.dev.oduist.com, FS_LOG_LEVEL=debug, FS_SOFIA_LOG_LEVEL=2, SOUND_RATES=8000:16000, SOUND_TYPES=music:en-us-callie, EPMD=false, DUMPCAP=false
- elevenlabs (oduflow-svc-elevenlabs): running
  ...
```

**Observation:** Confirmed the FreeSWITCH auxiliary service is named `fs` so the next call can target it directly.

---

## Step 2. Pull FreeSWITCH logs and locate the failing call

**Tool:** `mcp__oduflow_oduist__get_service_logs`

**Arguments:**
```json
{ "name": "fs", "n_lines": 300 }
```

**Result (excerpt — the load-bearing lines):**
```
4d82fb13-5471-435d-91bf-a2f2de88838a EXECUTE sofia/external/+37256011234@... set(odoo_call_direction=inbound)
4d82fb13-5471-435d-91bf-a2f2de88838a EXECUTE sofia/external/+37256011234@... set(odoo_number_id=3)
Dialplan: ... Action transfer(1 XML default)
Dialplan: ... Action bridge(user/1@team.dev.oduist.com)
[WARNING] mod_dptools.c:4383 Can't find user [1@team.dev.oduist.com]
[NOTICE] switch_ivr_originate.c:3059 Cannot create outgoing channel of type [user] cause: [SUBSCRIBER_ABSENT]
[INFO]    mod_dptools.c:3635 Originate Failed.  Cause: SUBSCRIBER_ABSENT
nta.c:6897 incoming_reply() nta: sent 480 Temporarily Unavailable for INVITE (1)
```

**Observation:** FreeSWITCH transferred to extension `1` in the `default` context, which fell through to the generic `local_extension` → `bridge(user/1@...)` — user not registered → `SUBSCRIBER_ABSENT` → `480 Temporarily Unavailable` back to Twilio. Need to find where `1` came from.

---

## Step 3. Inspect `connect.number` id=3 via Odoo shell

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "19.0-connect-migrate",
  "python_code": "n = env['connect.number'].browse(3)\nprint('name:', n.display_name)\nfor f in sorted(n._fields):\n    try:\n        v = getattr(n, f)\n        if v and not callable(v):\n            print(f'  {f} = {v!r}')\n    except Exception as e:\n        print(f'  {f} = <err {e}>')"
}
```

**Result (excerpt):**
```
name: +37257237879
  destination = 'fs_fifo'
  fs_fifo_id = connect.fs_fifo(1,)
  phone_number = '+37257237879'
  friendly_name = 'Test DID'
```

**Observation:** DID is correctly routed to FS Queue id=1. Now check that queue.

---

## Step 4. Inspect `connect.fs_fifo` id=1

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "19.0-connect-migrate",
  "python_code": "f = env['connect.fs_fifo'].browse(1)\nfor fn in sorted(f._fields):\n    try:\n        v = getattr(f, fn)\n        if v and not callable(v):\n            print(f'  {fn} = {v!r}')\n    except Exception as e:\n        print(f'  {fn} = <err {e}>')"
}
```

**Result (excerpt):**
```
display_name = 'Test Q'
member_user_ids = connect.user(1,)
max_wait_time = 60
moh_sound = '$${hold_music}'
timeout_action = 'hangup'
```

**Observation:** No `exten` / `exten_number` fields in the output, meaning the queue had no linked extension. Cross-referenced with `connect_freeswitch/models/number.py:32-33` — the fallback is `str(self.fs_fifo_id.id)`, which is where the literal `1` in the dialplan `transfer(1 XML default)` originates. **Root cause confirmed.**

---

## Step 5. Apply the code change after committing locally

**Tool:** `mcp__oduflow_oduist__pull_and_apply`

**Arguments:**
```json
{ "env_name": "19.0-connect-migrate" }
```

**Result (excerpt):**
```
Upgraded modules: connect_freeswitch Container restarted.
Upgraded: connect_freeswitch
Changed files (4):
  - CLAUDE.md
  - connect_freeswitch/models/fs_fifo.py
  - connect_freeswitch/models/gateway.py
  - connect_freeswitch/views/fs_fifo_views.xml
...
Module connect_freeswitch loaded in 0.72s, 604 queries (+604 other)
30 modules loaded in 1.73s, 604 queries (+604 extra)
Registry loaded in 8.573s
```

**Observation:** Upgrade succeeded, container restarted. Ready for UI verification.

---

## Step 6. Reset admin password for UI verification

**Tool:** `mcp__oduflow_oduist__reset_admin_password`

**Arguments:**
```json
{ "env_name": "19.0-connect-migrate" }
```

**Result:**
```
Admin password has been reset successfully.
Login: admin
New password: test
```

**Observation:** Logged in via `agent-browser` as `admin` / `test`.

---

## Step 7. Confirm the new `is_exten_set` flag and create a queue without an extension

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "19.0-connect-migrate",
  "python_code": "q = env['connect.fs_fifo'].create({'name': 'No-Exten Queue'})\nenv.cr.commit()\nprint('created id:', q.id, 'exten:', q.exten, 'is_exten_set:', q.is_exten_set)\nprint('all:', env['connect.fs_fifo'].search([]).mapped('name'))"
}
```

**Result (excerpt):**
```
created id: 4 exten: connect.exten() is_exten_set: False
all: ['No-Exten Queue', 'Test Alert Queue', 'Test Q']
```

**Observation:** Computed flag returns `False` exactly when there is no linked `exten`. A hard browser reload then showed the row `No-Exten Queue` highlighted red by `decoration-danger="not exten_number"`, and the form-level alert was verified separately on a fresh `New` record.

---

## Step 8. Clean up test records

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "19.0-connect-migrate",
  "python_code": "env['connect.fs_fifo'].browse([2, 4]).unlink()\nenv.cr.commit()\nprint('remaining:', env['connect.fs_fifo'].search([]).mapped('name'))"
}
```

**Result (excerpt):**
```
User #1 deleted connect.fs_fifo records with IDs: [2, 4]
remaining: ['Test Q']
```

**Observation:** Environment returned to the pre-verification state.

---

## Outcome

- Root cause of the `SUBSCRIBER_ABSENT` call failure identified: FS Queue without a linked `connect.exten` makes `number.py:32-33` fall back to the numeric queue id as the transfer target, which no dialplan rule handles.
- UI now makes the misconfiguration visible: red form alert on `connect.fs_fifo` when `is_exten_set` is false, plus danger-decorated list rows.
- Shipped in commit `7baa22c` on `19.0-connect-migrate`; module upgrade and UI verification completed via Oduflow.
- Not fixed in this session: the fallback in `number.generate_dialplan` itself, and automatic extension creation on `connect.fs_fifo.create` — those are separate design decisions that would warrant their own ADR.
