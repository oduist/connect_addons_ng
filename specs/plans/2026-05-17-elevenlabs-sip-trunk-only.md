# ElevenLabs SIP-Trunk-Only Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ADR-020 — collapse the EL transport matrix to a single SIP-trunk path, delete the FastAPI relay, replace the relay's `start_call_event` hook with an EL Conversation Initiation Webhook on the Odoo side, and unify the bridge contract.

**Architecture:** Core `connect_elevenlabs` becomes a single Odoo deployable (no FastAPI service). Both bridges (`_twilio`, `_freeswitch`) emit only SIP bridge primitives (`<Dial><Sip>` or `sofia/gateway`). Personalization moves from the relay JSON-RPC to a public Odoo controller that EL calls at conversation start.

**Tech Stack:** Odoo 19.0 (Python 3.10+, Owl frontend), `twilio` Python SDK (only in `_twilio` bridge), FreeSWITCH XML dialplan (only in `_freeswitch` bridge), `requests` for EL REST. No tests will be written — `tests_suite/` is in **Unprotected Mode** (per `CLAUDE.md`); verification uses oduflow shell/install + agent-browser UI checks.

---

## File Structure

**Core `connect_elevenlabs/`:**
- Delete: `service/main.py`, `service/twilio_audio_interface.py` (entire `service/` dir).
- Modify: `__manifest__.py` (bump version), `models/agent.py` (drop SIP fields, add stub + helper + webhook hook), `models/call.py` (drop `elevenlabs_agent_start_call_event`), `models/settings.py` (drop `elevenlabs_agent_url`, drop `ping_agent`), `views/agent.xml` (drop SIP block), `views/settings.xml` (drop agent_url field + ping button), `controllers/main.py` (add `/connect_elevenlabs/conversation_init`).

**Twilio bridge `connect_elevenlabs_twilio/`:**
- Modify: `__manifest__.py` (bump version), `models/agent.py` (drop `twilio_transport`, simplify `render()`, dedupe `transfer()`), `views/agent.xml` (drop transport selector + media_stream alert).

**FreeSWITCH bridge `connect_elevenlabs_freeswitch/`:**
- Modify: `__manifest__.py` (bump version), `models/agent.py` (drop `fs_transport` + constraint, simplify `generate_dialplan()`, dedupe `transfer()`), `views/agent.xml` (drop transport selector), `data/templates.xml` (drop `dialplan_elevenlabs_audio_stream` record).

**Decisions/docs:**
- Modify: `specs/decisions/015-elevenlabs-freeswitch-transport.md`, `specs/decisions/017-elevenlabs-twilio-sip-trunk.md`, `specs/decisions/019-elevenlabs-sip-trunk-per-agent.md` (add `Superseded by ADR-020`).
- Modify: `docs/admin/elevenlabs-setup.md`, `docs/admin/elevenlabs-twilio.md`, `docs/admin/elevenlabs-freeswitch.md` (drop relay/audio_fork/media_stream sections, add Conversation Initiation Webhook setup).

---

## Verification Mode

`tests_suite/` is **Unprotected Mode** (broken symlinks, no Python tests to run). Per `CLAUDE.md§Self-driven verification`, each task verifies via one of:

- **Install smoke:** `oduflow upgrade_odoo_modules <module>` — must complete with no traceback.
- **Server-side state:** `oduflow run_odoo_shell` with a one-liner — confirms a field/method is gone or behaves as expected.
- **UI:** `agent-browser` snapshot of the form view — confirms a field/tab is gone.
- **Webhook:** `oduflow http_request_to_odoo` — confirms a route exists and responds with the expected JSON.
- **Dialplan render:** `oduflow run_service_command freeswitch fs_cli -x "..."` — confirms a SIP bridge succeeds end-to-end.

Active Oduflow environment is assumed (`<current branch>` — `19.0-elevenlabs`). If absent, create one before Task 1: `mcp__oduflow__create_environment env_name="19.0-elevenlabs"`.

---

### Task 1: Delete the FastAPI relay service

**Files:**
- Delete: `connect_elevenlabs/service/main.py`
- Delete: `connect_elevenlabs/service/twilio_audio_interface.py`
- Delete: `connect_elevenlabs/service/` directory (empty after the two deletes)

- [ ] **Step 1:** Confirm nothing in the Odoo addon imports from `service/`:

```bash
grep -rn "from .service\|from connect_elevenlabs.service\|import service" connect_elevenlabs/ 2>/dev/null
```

Expected: no output (the relay is a standalone Docker deployable, not loaded by Odoo).

- [ ] **Step 2:** Delete the relay files:

```bash
rm -rf connect_elevenlabs/service/
```

- [ ] **Step 3:** Bump `connect_elevenlabs/__manifest__.py` version `1.0.5` → `1.1.0` (major refactor):

```python
'version': '1.1.0',
```

- [ ] **Step 4:** Verify the module still installs:

Use `mcp__oduflow__upgrade_odoo_modules` with `module_names=["connect_elevenlabs"]`. Expected: success, no traceback.

- [ ] **Step 5:** Commit:

```bash
git add connect_elevenlabs/__manifest__.py
git add -u connect_elevenlabs/service/
git commit -m "[connect_elevenlabs] remove FastAPI relay service (ADR-020)"
```

---

### Task 2: Drop relay settings (`elevenlabs_agent_url` + `ping_agent`)

**Files:**
- Modify: `connect_elevenlabs/models/settings.py`
- Modify: `connect_elevenlabs/views/settings.xml`

- [ ] **Step 1:** Open `connect_elevenlabs/models/settings.py` and delete the field definition (line 35):

Old:
```python
elevenlabs_agent_url = fields.Char(string='Agent URL', required=True, default='https://elevenlabs-agent.ngrok.io')
```

Delete the line.

- [ ] **Step 2:** Delete the `ping_agent()` method (lines ~165-174):

```python
def ping_agent(self):
    self.ensure_one()
    try:
        response = requests.post(urljoin(self.elevenlabs_agent_url, '/agent/ping'))
        if response.text == 'true':
            self.connect_notify('Pong', title='Elevenlabs Agent', notify_uid=self.env.user.id)
        else:
            self.connect_notify('Error! Check the Agent error log.', title='Elevenlabs Agent', notify_uid=self.env.user.id)
    except Exception as e:
        raise ValidationError(str(e))
```

Delete the entire method.

- [ ] **Step 3:** Open `connect_elevenlabs/views/settings.xml` and delete the field reference at line 98:

```xml
<field name="elevenlabs_agent_url"/>
```

Plus the `<button name="ping_agent" ...>` reference (search for `ping_agent` in the file).

- [ ] **Step 4:** Confirm nothing else still references the removed names:

```bash
grep -rn "elevenlabs_agent_url\|ping_agent" connect_elevenlabs/ connect_elevenlabs_twilio/ connect_elevenlabs_freeswitch/ connect_elevenlabs_helpdesk/ connect_elevenlabs_knowledge/ connect_elevenlabs_sale/
```

Expected: no hits (the `_twilio` and `_freeswitch` `elevenlabs_agent_url` references will be removed in Tasks 5 and 6 — flag them now and address there).

- [ ] **Step 5:** Upgrade module:

`mcp__oduflow__upgrade_odoo_modules module_names=["connect_elevenlabs"]`. Expected: success.

- [ ] **Step 6:** UI check via agent-browser — Settings form has no Agent URL field and no Ping button:

```
agent-browser open <env URL>/odoo/action-base_setup.action_general_configuration
agent-browser snapshot -i
```

(Look in the ElevenLabs settings tab.) Expected: no `Agent URL` row, no `Ping` button.

- [ ] **Step 7:** Commit:

```bash
git add connect_elevenlabs/models/settings.py connect_elevenlabs/views/settings.xml
git commit -m "[connect_elevenlabs] drop elevenlabs_agent_url and ping_agent (ADR-020)"
```

---

### Task 3: Drop dead per-agent SIP fields

**Files:**
- Modify: `connect_elevenlabs/models/agent.py`
- Modify: `connect_elevenlabs/views/agent.xml`

- [ ] **Step 1:** In `connect_elevenlabs/models/agent.py`, delete the SIP block (lines 190-223). Remove:

```python
# SIP trunk per-agent (ADR-019)
sip_enabled = fields.Boolean(default=False, string="Enable SIP Trunk")
sip_inbound_addresses = fields.Char(...)
sip_outbound_addresses = fields.Char(...)
sip_allowed_numbers = fields.Char(...)
sip_override_credentials = fields.Boolean(...)
sip_username = fields.Char(...)
sip_password = fields.Char(...)

def _resolve_sip_credentials(self):
    ...
```

Delete all 7 field declarations and the entire `_resolve_sip_credentials` method.

- [ ] **Step 2:** In `connect_elevenlabs/views/agent.xml`, delete the SIP block (lines ~100-115). Remove the `<field name="sip_enabled"/>`, `<div invisible="sip_enabled">...</div>`, `<group invisible="not sip_enabled">...</group>` block.

- [ ] **Step 3:** Confirm no consumers:

```bash
grep -rn "sip_enabled\|sip_inbound_addresses\|sip_outbound_addresses\|sip_allowed_numbers\|sip_override_credentials\|_resolve_sip_credentials" connect_elevenlabs/ connect_elevenlabs_twilio/ connect_elevenlabs_freeswitch/
```

Note: `sip_enabled` will still match `connect_twilio/models/user.py` (a different field on `connect.user`). That's unrelated — keep that match.

Expected: no hits inside the `connect_elevenlabs*` modules.

- [ ] **Step 4:** Upgrade + verify the field is gone:

`mcp__oduflow__upgrade_odoo_modules module_names=["connect_elevenlabs"]`. Then via `mcp__oduflow__run_odoo_shell`:

```python
'sip_enabled' in env['connect.elevenlabs_agent']._fields
```

Expected: `False`.

- [ ] **Step 5:** Commit:

```bash
git add connect_elevenlabs/models/agent.py connect_elevenlabs/views/agent.xml
git commit -m "[connect_elevenlabs] drop per-agent SIP-trunk fields (ADR-020 supersedes ADR-019)"
```

---

### Task 4: Drop the relay's `start_call_event` JSON-RPC entry

**Files:**
- Modify: `connect_elevenlabs/models/call.py`

`elevenlabs_agent_get_call_data` is kept — `connect_elevenlabs_sale/models/call.py` overrides it via `super()`. Only the relay-facing `elevenlabs_agent_start_call_event` (lines 69-78) is deleted.

- [ ] **Step 1:** In `connect_elevenlabs/models/call.py`, delete:

```python
@api.model
def elevenlabs_agent_start_call_event(self, params):
    call_id=params['call_id']
    agent_uid=params['agent_uid']
    # aio_odoorpc cannot pass positional args?
    call = self.sudo().browse(int(call_id))
    agent = self.env['connect.elevenlabs_agent'].sudo().search([('agent_uid', '=', agent_uid)])
    # Link call to the Agent.
    call.elevenlabs_agent = agent.id
    return call.elevenlabs_agent_get_call_data()
```

- [ ] **Step 2:** Confirm no in-repo callers (only the deleted relay called it):

```bash
grep -rn "elevenlabs_agent_start_call_event" connect_elevenlabs/ connect_elevenlabs_twilio/ connect_elevenlabs_freeswitch/ connect_elevenlabs_helpdesk/ connect_elevenlabs_knowledge/ connect_elevenlabs_sale/
```

Expected: no hits.

- [ ] **Step 3:** Confirm `elevenlabs_agent_get_call_data` is still defined (sale override depends on it):

```bash
grep -n "def elevenlabs_agent_get_call_data" connect_elevenlabs/models/call.py connect_elevenlabs_sale/models/call.py
```

Expected: two hits (one in core, one in sale).

- [ ] **Step 4:** Upgrade:

`mcp__oduflow__upgrade_odoo_modules module_names=["connect_elevenlabs", "connect_elevenlabs_sale"]`. Expected: success.

- [ ] **Step 5:** Commit:

```bash
git add connect_elevenlabs/models/call.py
git commit -m "[connect_elevenlabs] drop relay start_call_event hook (ADR-020)"
```

---

### Task 5: Twilio bridge — collapse to SIP-only + dedupe transfer

**Files:**
- Modify: `connect_elevenlabs_twilio/__manifest__.py`
- Modify: `connect_elevenlabs_twilio/models/agent.py`
- Modify: `connect_elevenlabs_twilio/views/agent.xml`

- [ ] **Step 1:** Open `connect_elevenlabs_twilio/models/agent.py` and replace the entire `render()` method + drop the `twilio_transport` field. New content of the class (delete the field declaration `twilio_transport = fields.Selection(...)`; keep `twilio_sip_host`):

```python
class ElevenlabsAgent(models.Model):
    _inherit = 'connect.elevenlabs_agent'

    twilio_sip_host = fields.Char(
        string='ElevenLabs SIP Host',
        default='sip.elevenlabs.io',
        help="SIP host of the ElevenLabs inbound trunk.",
    )

    def render(self, request, params=None):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect_elevenlabs'):
            return (
                "<Response><Pause length='1'/>"
                "<Say>This is Oduist Connect. Your trial period is over. "
                "Please buy a license to continue.</Say>"
                "<Pause length='1'/></Response>"
            )
        channel_sid = request.get('CallSid')
        host = self.twilio_sip_host or 'sip.elevenlabs.io'
        response = VoiceResponse()
        dial = Dial()
        dial.sip(f"sip:{self.agent_uid}@{host}?X-Call-Sid={channel_sid}")
        response.append(dial)
        debug(self, pretty_xml(response))
        return response
```

Also drop the now-unused `Connect` import on line 7 — change `from twilio.twiml.voice_response import Connect, Dial, VoiceResponse` to `from twilio.twiml.voice_response import Dial, VoiceResponse`.

- [ ] **Step 2:** Replace the duplicated extension-resolution block in `transfer()` with the core helper. New `transfer()`:

```python
@api.model
def transfer(self, channel_sid=None, exten=None):
    logger.info("Transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
    if not channel_sid or not exten:
        return "Not all parameters passed. You must provide channel_sid and exten (only digits)"
    exten_rec, err = self._resolve_transfer_target(exten)
    if err:
        return err
    self = self.sudo()
    client = self.env['connect.settings'].get_client()
    channel = self.env['connect.channel'].search([('sid', '=', channel_sid)])
    twiml = exten_rec.render(
        {"Caller": channel.caller, "Called": channel.called, "CallSid": channel.sid}
    )
    debug(self, "Transfer to: {}".format(pretty_xml(twiml)))
    client.calls(channel_sid).update(twiml=twiml)
    return "Transfer Successful"
```

(`_resolve_transfer_target` is added on the core agent in Task 7 — order matters; do Task 7 *before* Tasks 5/6 if executing serially, or stage both and commit Task 7 first.)

- [ ] **Step 3:** Open `connect_elevenlabs_twilio/views/agent.xml`. Replace the entire `<page name="twilio">` block content with a single SIP-only group:

```xml
<page name="twilio" string="Twilio">
    <group>
        <field name="twilio_sip_host"/>
    </group>
    <div class="alert alert-info" role="alert">
        <strong>SIP Trunk:</strong>
        Provision an inbound SIP trunk in the ElevenLabs dashboard
        and bind it to this agent. Twilio's
        <code>&lt;Dial&gt;&lt;Sip&gt;</code> hands the call straight
        to ElevenLabs over SIP. Transfer back relies on ElevenLabs
        forwarding the <code>X-Call-Sid</code> header in webhooks.
    </div>
</page>
```

- [ ] **Step 4:** Bump version in `connect_elevenlabs_twilio/__manifest__.py`: `1.0.0` → `1.1.0`.

- [ ] **Step 5:** Confirm no leftover references to removed names:

```bash
grep -rn "twilio_transport\|media_stream\|elevenlabs_agent_url" connect_elevenlabs_twilio/
```

Expected: no hits.

- [ ] **Step 6:** Upgrade + verify field is gone:

`mcp__oduflow__upgrade_odoo_modules module_names=["connect_elevenlabs_twilio"]`. Then:

```python
'twilio_transport' in env['connect.elevenlabs_agent']._fields  # False
'twilio_sip_host'  in env['connect.elevenlabs_agent']._fields  # True
```

- [ ] **Step 7:** Commit:

```bash
git add connect_elevenlabs_twilio/
git commit -m "[connect_elevenlabs_twilio] sip-trunk only render + dedupe transfer (ADR-020)"
```

---

### Task 6: FreeSWITCH bridge — collapse to SIP-only + dedupe transfer

**Files:**
- Modify: `connect_elevenlabs_freeswitch/__manifest__.py`
- Modify: `connect_elevenlabs_freeswitch/models/agent.py`
- Modify: `connect_elevenlabs_freeswitch/views/agent.xml`
- Modify: `connect_elevenlabs_freeswitch/data/templates.xml`

- [ ] **Step 1:** In `connect_elevenlabs_freeswitch/models/agent.py`, drop the `fs_transport` field declaration (lines 17-29), the `_check_fs_transport_audio_format` constraint (lines 31-43), the `AUDIO_FORK_FORMAT` constant (line 11), and the `audio_fork` branch in `generate_dialplan()` (lines 70-84). Result for the class:

```python
FS_GATEWAY_NAME = 'elevenlabs'


class ElevenlabsAgent(models.Model):
    _inherit = 'connect.elevenlabs_agent'

    def generate_dialplan(self, params, exten=None):
        """Render FS dialplan that bridges the inbound call to ElevenLabs
        over the SIP gateway."""
        self.ensure_one()
        if not exten:
            logger.warning(
                "generate_dialplan called for agent %s without exten", self.id)
            return ''
        if not self.agent_uid:
            logger.warning(
                "Agent %s has no agent_uid; cannot bridge", self.id)
            return ''
        Template = self.env['connect.freeswitch.template'].sudo()
        return Template.render('dialplan_elevenlabs_sip', {
            'extension_number': exten.number,
            'agent_uid': self.agent_uid,
            'gateway_name': FS_GATEWAY_NAME,
        })
```

Also drop the now-unused `ValidationError` import on line 5 if nothing else uses it (the constraint was the only consumer).

- [ ] **Step 2:** Replace the duplicated extension-resolution block in `transfer()` with the core helper:

```python
@api.model
def transfer(self, channel_sid=None, exten=None):
    logger.info("FS transfer request: exten=%s, channel_sid=%s", exten, channel_sid)
    if not channel_sid or not exten:
        return ("Not all parameters passed. You must provide "
                "channel_sid and exten (only digits)")
    exten_rec, err = self._resolve_transfer_target(exten)
    if err:
        return err
    self = self.sudo()
    channel = self.env['connect.channel'].search(
        [('sid', '=', channel_sid)], limit=1)
    if not channel:
        return "Channel %s not found" % channel_sid
    result = self.env['connect.settings'].freeswitch_api(
        'uuid_transfer',
        '{} {} XML default'.format(channel.sid, exten_rec.number))
    if result is False:
        return "FreeSWITCH transfer failed (XML-RPC unreachable)"
    return "Transfer Successful"
```

- [ ] **Step 3:** In `connect_elevenlabs_freeswitch/data/templates.xml`, delete the entire `<record id="fs_template_dialplan_elevenlabs_audio_stream" ...>` block (lines 39-70).

- [ ] **Step 4:** In `connect_elevenlabs_freeswitch/views/agent.xml`, replace the `<page name="freeswitch">` content (remove the `<field name="fs_transport"/>`). Final shape:

```xml
<page name="freeswitch" string="FreeSWITCH">
    <div class="alert alert-info" role="alert">
        <strong>SIP Trunk:</strong>
        Provision a SIP trunk in the ElevenLabs dashboard, then create a
        <code>connect.freeswitch.gateway</code> record named
        <code>elevenlabs</code> with the credentials it provides. See
        <em>docs/admin/elevenlabs-freeswitch.md</em>.
    </div>
</page>
```

- [ ] **Step 5:** Bump version in `connect_elevenlabs_freeswitch/__manifest__.py`: `1.0.0` → `1.1.0`.

- [ ] **Step 6:** Confirm no leftover references:

```bash
grep -rn "fs_transport\|audio_fork\|audio_stream\|AUDIO_FORK_FORMAT" connect_elevenlabs_freeswitch/
```

Expected: no hits.

- [ ] **Step 7:** Upgrade + verify:

`mcp__oduflow__upgrade_odoo_modules module_names=["connect_elevenlabs_freeswitch"]`. Then:

```python
'fs_transport' in env['connect.elevenlabs_agent']._fields  # False
bool(env.ref('connect_elevenlabs_freeswitch.fs_template_dialplan_elevenlabs_audio_stream', raise_if_not_found=False))  # False
```

- [ ] **Step 8:** Commit:

```bash
git add connect_elevenlabs_freeswitch/
git commit -m "[connect_elevenlabs_freeswitch] sip-trunk only dialplan + dedupe transfer (ADR-020)"
```

---

### Task 7: Core agent — unified bridge stubs + `_resolve_transfer_target` helper

**Files:**
- Modify: `connect_elevenlabs/models/agent.py`

> **Ordering note:** Execute this task **before** Tasks 5 and 6 — they call `_resolve_transfer_target`. Recommended execution order: 1 → 2 → 3 → 4 → 7 → 5 → 6 → 8 → 9 → 10 → 11.

- [ ] **Step 1:** Open `connect_elevenlabs/models/agent.py`. Locate the existing `render()` and `transfer()` stubs (lines 329-345). Replace them and add `generate_dialplan` + `_resolve_transfer_target`:

```python
def render(self, request, params=None):
    """Twilio bridge entry — returns TwiML.
    Overridden in connect_elevenlabs_twilio."""
    self.ensure_one()
    logger.warning(
        "connect.elevenlabs_agent.render: no Twilio bridge installed.")
    return ''

def generate_dialplan(self, params, exten=None):
    """FreeSWITCH bridge entry — returns dialplan XML.
    Overridden in connect_elevenlabs_freeswitch."""
    self.ensure_one()
    logger.warning(
        "connect.elevenlabs_agent.generate_dialplan: no FreeSWITCH bridge installed.")
    return ''

@api.model
def transfer(self, channel_sid=None, exten=None):
    """Transfer-tool callback — overridden by each bridge to drive the
    provider-specific REST/ESL call."""
    logger.warning(
        "connect.elevenlabs_agent.transfer: no provider bridge installed.")
    return "ElevenLabs transfer requires a provider bridge (Twilio/FreeSWITCH)."

def _resolve_transfer_target(self, exten_str):
    """Resolve a transfer-tool 'exten' argument to a connect.exten record.

    Returns (exten_rec, None) on success or (None, error_message) on
    failure, where error_message is the human-readable string returned
    to ElevenLabs by the bridge's transfer() implementation.
    """
    if isinstance(exten_str, str) and not exten_str.isalnum():
        return None, "Wrong extension format. Only digits, e.g. 101"
    Exten = self.env['connect.exten'].sudo()
    exten_rec = Exten.search([('number', '=', str(exten_str).strip())], limit=1)
    if exten_rec:
        return exten_rec, None
    published = Exten.search([('is_published', '=', True)])
    if not published:
        return None, ("There is no public extension to connect the call. "
                      "Cannot transfer")
    if len(published) == 1:
        logger.info(
            "Extension %s not found; falling back to single published %s",
            exten_str, published.number)
        return published, None
    available = ", ".join(
        '<{}> "{}"'.format(p.number, p.dst.name if p.dst else '')
        for p in published)
    return None, ("Extension {} not found. Available extensions: {}. "
                  "Please try again with a correct number.".format(
                      exten_str, available))
```

- [ ] **Step 2:** Upgrade + smoke test:

`mcp__oduflow__upgrade_odoo_modules module_names=["connect_elevenlabs"]`. Then via `run_odoo_shell`:

```python
agent = env['connect.elevenlabs_agent'].search([], limit=1)
agent._resolve_transfer_target("999999")  # (False, "There is no public extension..." or "Extension 999999 not found...")
agent._resolve_transfer_target("abc!")    # (False, "Wrong extension format...")
```

Expected: tuples per docstring.

- [ ] **Step 3:** Commit:

```bash
git add connect_elevenlabs/models/agent.py
git commit -m "[connect_elevenlabs] unify bridge stubs and add _resolve_transfer_target helper (ADR-020)"
```

---

### Task 8: Conversation Initiation Webhook — controller + agent payload helper

**Files:**
- Modify: `connect_elevenlabs/controllers/main.py`
- Modify: `connect_elevenlabs/models/agent.py`

The new controller replaces the relay's `start_call_event`. Auth: HMAC by `elevenlabs_post_call_webhook_secret` (same primitive already used for `/connect_elevenlabs/post_call`). Payload: EL POSTs `{caller_id, called_id, agent_id, conversation_id}` (E.164 strings). Optional `call_id`: passed by the bridge as a SIP header (`X-Call-Id`) that EL relays as a dynamic variable.

- [ ] **Step 1:** In `connect_elevenlabs/models/agent.py`, add the payload-build helper just below `_resolve_transfer_target`:

```python
def _build_conversation_init_response(self, caller_id, called_id, call_id=None):
    """Build the JSON body EL expects from a Conversation Initiation
    Webhook. If call_id is provided, reuses the (sale-override-aware)
    elevenlabs_agent_get_call_data() on the existing connect.call;
    otherwise resolves the partner from caller_id alone and returns
    a minimal dynamic_variables block."""
    self.ensure_one()
    Call = self.env['connect.call'].sudo()
    call = Call.browse(int(call_id)) if call_id else Call.browse()
    if not call.exists():
        # Best-effort match by caller+called (newest call this minute).
        call = Call.search(
            [('caller', '=', caller_id), ('called', '=', called_id)],
            order='id desc', limit=1)
    if call:
        if not call.elevenlabs_agent:
            call.elevenlabs_agent = self.id
        dynamic_variables = call.elevenlabs_agent_get_call_data()
    else:
        # No call record — return a minimal payload.
        partner = self.env['res.partner'].sudo().search(
            [('phone', '=', caller_id)], limit=1)
        dynamic_variables = {
            'caller_number': caller_id,
            'called_number': called_id,
            'partner_name': partner.name or 'Not registered',
            'existing_partner': 'Yes' if partner else 'No',
            'partner_id': partner.id,
            'greeting': partner.name or 'Dear customer',
            'previous_conversation_id': '',
            'previous_topics': '',
        }
    lang = dynamic_variables.get('partner_language') or self.language
    return {
        'type': 'conversation_initiation_client_data',
        'dynamic_variables': dynamic_variables,
        'conversation_config_override': {
            'agent': {'language': lang},
        },
    }
```

- [ ] **Step 2:** In `connect_elevenlabs/controllers/main.py`, add the new route after the existing `post_call_webhook`:

```python
@http.route('/connect_elevenlabs/conversation_init',
            methods=['POST'], type='http', auth='public', csrf=False)
def conversation_init_webhook(self):
    logger.info('Incoming request: /connect_elevenlabs/conversation_init')
    if not self.check_post_call_webhook():
        raise Unauthorized()
    payload = json.loads(http.request.httprequest.get_data(as_text=True))
    data = payload.get('data') or payload
    agent_id = data.get('agent_id')
    caller_id = data.get('caller_id') or data.get('from_number')
    called_id = data.get('called_id') or data.get('to_number')
    call_id = (data.get('dynamic_variables') or {}).get('call_id')
    agent = http.request.env['connect.elevenlabs_agent'].with_user(
        http.request.env.ref('connect.user_connect_webhook')).sudo().search(
        [('agent_uid', '=', agent_id)], limit=1)
    if not agent:
        logger.warning('conversation_init: no agent for agent_id=%s', agent_id)
        return http.request.make_response(
            json.dumps({'type': 'conversation_initiation_client_data',
                        'dynamic_variables': {}}),
            headers=[('Content-Type', 'application/json')])
    response = agent._build_conversation_init_response(
        caller_id, called_id, call_id=call_id)
    return http.request.make_response(
        json.dumps(response),
        headers=[('Content-Type', 'application/json')])
```

- [ ] **Step 3:** Upgrade:

`mcp__oduflow__upgrade_odoo_modules module_names=["connect_elevenlabs"]`. Expected: success.

- [ ] **Step 4:** Smoke-test the route returns JSON (auth will fail without valid HMAC, but we just want a 401 — not a 404):

Use `mcp__oduflow__http_request_to_odoo` with `path="/connect_elevenlabs/conversation_init"`, `method="POST"`, `body='{}'`. Expected: HTTP 401 (Unauthorized), not 404.

- [ ] **Step 5:** Commit:

```bash
git add connect_elevenlabs/models/agent.py connect_elevenlabs/controllers/main.py
git commit -m "[connect_elevenlabs] add EL Conversation Initiation Webhook (ADR-020)"
```

---

### Task 9: Auto-push webhook URL to EL on agent sync

**Files:**
- Modify: `connect_elevenlabs/models/agent.py`

So that the per-agent override URL stays in lockstep with the Odoo route, `_build_platform_settings()` includes the webhook URL based on the request's base URL (or `web.base.url`).

- [ ] **Step 1:** In `connect_elevenlabs/models/agent.py`, locate `_build_platform_settings` (around line 534). Extend it to include the webhook URL:

```python
def _build_platform_settings(self) -> AgentPlatformSettingsRequestModel:
    """Build proper AgentPlatformSettingsRequestModel object using new API types"""
    base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
    webhook_url = (base_url.rstrip('/')
                   + '/connect_elevenlabs/conversation_init') if base_url else None
    workspace = {}
    if webhook_url:
        workspace['conversation_initiation_client_data_webhook'] = {
            'url': webhook_url,
            'request_headers': {},
        }
    return AgentPlatformSettingsRequestModel(
        overrides={
            "conversation_config_override": {
                "agent": {"language": True},
            },
        },
        call_limits={
            "agent_concurrency_limit": self.agent_concurrency_limit,
            "daily_limit": self.daily_limit,
        },
        workspace_overrides=workspace or None,
    )
```

If `AgentPlatformSettingsRequestModel` does not accept `workspace_overrides` directly, fall back to `model_construct`:

```python
return AgentPlatformSettingsRequestModel.model_construct(
    overrides=..., call_limits=..., workspace_overrides=workspace or None,
)
```

- [ ] **Step 2:** Upgrade + trigger a sync on one existing agent:

`mcp__oduflow__run_odoo_shell` with:

```python
a = env['connect.elevenlabs_agent'].search([], limit=1)
a.update_elevenlabs_agent()
```

Expected: no exception. Manually verify in the EL dashboard that the agent's "Custom LLM" / "Conversation Initiation Webhook" field now points at `<base_url>/connect_elevenlabs/conversation_init`.

- [ ] **Step 3:** Commit:

```bash
git add connect_elevenlabs/models/agent.py
git commit -m "[connect_elevenlabs] auto-push conversation_init webhook URL on agent sync (ADR-020)"
```

---

### Task 10: Mark ADRs 015/017/019 as Superseded

**Files:**
- Modify: `specs/decisions/015-elevenlabs-freeswitch-transport.md`
- Modify: `specs/decisions/017-elevenlabs-twilio-sip-trunk.md`
- Modify: `specs/decisions/019-elevenlabs-sip-trunk-per-agent.md`

- [ ] **Step 1:** In each file, change the front-matter line:

```
**Status:** Accepted
```

to:

```
**Status:** Superseded by ADR-020
```

- [ ] **Step 2:** Commit:

```bash
git add specs/decisions/015-elevenlabs-freeswitch-transport.md \
        specs/decisions/017-elevenlabs-twilio-sip-trunk.md \
        specs/decisions/019-elevenlabs-sip-trunk-per-agent.md
git commit -m "[connect_elevenlabs] mark ADR-015/017/019 as superseded by ADR-020"
```

---

### Task 11: Update admin docs

**Files:**
- Modify: `docs/admin/elevenlabs-setup.md`
- Modify: `docs/admin/elevenlabs-freeswitch.md`

`docs/admin/elevenlabs-twilio.md` does not exist (ADR-017 listed it as a follow-up that was never written). Creating it is out of scope here; the Twilio setup is described inline in `elevenlabs-setup.md`.

- [ ] **Step 1:** In `docs/admin/elevenlabs-setup.md`:
  - Delete any section that talks about deploying the FastAPI relay, the `elevenlabs_agent_url` setting, the "Ping" button, or the `twilio_transport` / `media_stream` field.
  - Add a new section **"Conversation Initiation Webhook"** explaining: when an agent is saved, `update_elevenlabs_agent()` writes the webhook URL into the agent's platform settings on ElevenLabs (`<base_url>/connect_elevenlabs/conversation_init`). The route is HMAC-authenticated by `elevenlabs_post_call_webhook_secret`.

- [ ] **Step 2:** In `docs/admin/elevenlabs-freeswitch.md`:
  - Delete the "Audio Fork" / `mod_audio_fork` / `audio_stream` section.
  - The remaining content is the SIP-trunk setup (gateway provisioning, dialplan template). Update the lead paragraph to say there is now a single transport.

- [ ] **Step 3:** Verify cross-references in other doc files don't break:

```bash
grep -rn "elevenlabs_agent_url\|media_stream\|audio_fork\|audio_stream\|ping_agent\|twilio_transport\|fs_transport" docs/
```

Expected: no hits.

- [ ] **Step 4:** Commit:

```bash
git add docs/admin/elevenlabs-setup.md docs/admin/elevenlabs-freeswitch.md
git commit -m "[connect_elevenlabs] docs: drop relay/media_stream/audio_fork sections (ADR-020)"
```

---

### Task 12: End-to-end smoke test

**No file changes.** Verify all three modules still work together.

- [ ] **Step 1:** Reset admin password and open the app:

`mcp__oduflow__reset_admin_password env_name="19.0-elevenlabs"` → login `admin` / `test`.

- [ ] **Step 2:** Open the EL agent form. Confirm:
  - No "SIP Trunk" group on the main page (Task 3).
  - "Twilio" tab has only `twilio_sip_host` field (Task 5).
  - "FreeSWITCH" tab has only the alert text, no `fs_transport` selector (Task 6).

- [ ] **Step 3:** Settings form: confirm no Agent URL field and no Ping button (Task 2).

- [ ] **Step 4:** From a registered SIP softphone (or via `fs_cli -x "originate ..."` per `CLAUDE.md§Testing FreeSWITCH SIP Calls`), place a call to an extension routed to an EL agent. Expected: call connects, agent speaks first-message, transfer tool works.

- [ ] **Step 5:** Hang up. Verify within ~30 s that the post-call webhook fires: `connect.recording` for that call has `elevenlabs_transcript` populated, `connect.call.elevenlabs_summary` set.

- [ ] **Step 6:** Done. No further commits.

---

## Out of scope

Tracked here so the reviewer doesn't expect them in this plan:

- `connect_elevenlabs/models/agent.py:91` Cyrillic comment cleanup (separate housekeeping commit).
- Restoring relay as an opt-in deployable (future ADR if/when needed for analytics/audio-mux).
- Per-number SIP-trunk provisioning via `POST /v1/convai/phone-numbers` (future ADR with real consumer).
- Outbound calls originated by ElevenLabs.
