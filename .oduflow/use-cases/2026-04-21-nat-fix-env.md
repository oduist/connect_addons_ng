# nat-fix-env — 2026-04-21

**Branch:** `litnimax/fix-sip-ring-both`
**Goal:** Provision a disposable FreeSWITCH test environment to validate NAT handling fixes for SIP phones registering from behind NAT.
**Related files/PR:** `connect_freeswitch/data/fs_templates.xml`, `connect_freeswitch/views/fs_template_views.xml`, `specs/decisions/012-freeswitch-nat-handling.md`

## Context

A SIP softphone (Acrobits) registering from behind NAT advertised a private Contact IP (`192.168.0.197`). Outgoing calls worked because NAT pinholes were open, but inbound INVITEs were sent to the unreachable private IP and timed out. The fix adds `aggressive-nat-detection`, `NDLB-received-in-nat-reg-contact`, `nat-options-ping`, and `apply-nat-acl=rfc1918.auto` to the sofia profile template.

To verify the fix end-to-end (module upgrade, SIP registration, incoming call flow) without touching any shared environment, an isolated Oduflow env was provisioned from the `fs19-dev` template on the feature branch.

---

## Step 1. Create environment from fs19-dev template

**Tool:** `mcp__oduflow_oduist__create_environment`

**Arguments:**
```json
{
  "branch": "litnimax/fix-sip-ring-both",
  "template_name": "fs19-dev"
}
```

**Result:**
```
Environment provisioned successfully!
Environment: litnimax/fix-sip-ring-both
URL: https://litnimax-fix-sip-ring-both.team.dev.oduist.com
Odoo Container: oduflow-litnimax-fix-sip-ring-both-odoo
Database: oduflow_2_litnimax-fix-sip-ring-both
Workspace: /srv/oduflow/team_2/workspaces/litnimax-fix-sip-ring-both
Template: fs19-dev
Creation time: 54.8s
```

<details>
<summary>Setup log (pip install + sanitize)</summary>

```
[PIP] Requirements installed successfully:
WARNING: Skipping /usr/lib/python3.12/dist-packages/charset_normalizer-3.3.2.dist-info due to invalid metadata entry 'name'
Collecting openai (from -r /mnt/extra-addons/requirements.txt (line 1))
  Downloading openai-2.30.0-py3-none-any.whl.metadata (29 kB)
Collecting pyjwt (from -r /mnt/extra-addons/requirements.txt (line 2))
  Downloading pyjwt-2.12.1-py3-none-any.whl.metadata (4.1 kB)
Collecting twilio (from -r /mnt/extra-addons/requirements.txt (line 3))
  Downloading twilio-9.10.4-py2.py3-none-any.whl.metadata (13 kB)
...
Successfully installed aiohappyeyeballs-2.6.1 aiohttp-3.13.5 aiohttp-retry-2.9.1 annotated-types-0.7.0 anyio-4.13.0 distro-1.9.0 frozenlist-1.8.0 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 jiter-0.13.0 multidict-6.7.1 openai-2.30.0 propcache-0.4.1 pydantic-2.12.5 pydantic-core-2.41.5 pyjwt-2.12.1 sniffio-1.3.1 tqdm-4.67.3 twilio-9.10.4 typing-extensions-4.15.0 typing-inspection-0.4.2 yarl-1.23.0

[SANITIZE:system] Executed 01_disable_mail.sql
```

</details>

**Observation:** Provisioning took ~55s. The `fs19-dev` template bundled all required services (Odoo + FreeSWITCH), so no extra repos or services had to be added manually. Environment URL became immediately available for SIP phone registration testing.

---

## Outcome

Isolated test environment is live at `https://litnimax-fix-sip-ring-both.team.dev.oduist.com` and tracks the `litnimax/fix-sip-ring-both` branch. Next steps (not yet executed via Oduflow): upgrade the `connect_freeswitch` module inside the env, register a SIP phone behind NAT, verify that `sofia status profile external reg` shows the public contact IP, and confirm an inbound call rings the phone.
