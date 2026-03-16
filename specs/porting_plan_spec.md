# Porting Plan: License & Registration System

## Source → Target

- **Source**: `/workspace/odoo19/addons_connect/connect/` (monolithic)
- **Target**: `/workspace/odoo19/addons_connect_ng/connect/` (modular core)

---

## 1. Overview

The license system is a self-contained subsystem in the old `connect` module providing:

1. **`oduist.license` model** — single-record model storing JWT license token, instance UID, registration number, subscription preferences
2. **`ir.module.module` extension** — adds license status, pricing, and purchase button to module records
3. **License banner (frontend)** — systray OWL component showing trial/expiry status
4. **License enforcement** — `check_license()` calls scattered across business models (call, message, number, domain, whatsapp_sender)
5. **Post-init hook** — resets `create_date` on install and calls `update_license_status`
6. **`ODUIST_MODULES` registry** — mutable list populated by each module at import time

---

## 2. Files to Port

### 2.1 New Files to Create

| # | File (target) | Source | Description |
|---|---------------|--------|-------------|
| 1 | `connect/models/license.py` | `models/license.py` (500 lines) | `oduist.license` model — full copy, remove Twilio-specific references if any |
| 2 | `connect/models/ir_module_module.py` | `models/ir_module_module.py` (71 lines) | `ir.module.module` extension with license status fields |
| 3 | `connect/views/license.xml` | `views/license.xml` (67 lines) | Form view, server action, menu item |
| 4 | `connect/data/license.xml` | `data/license.xml` (19 lines) | `ir.config_parameter` for `oduist_license_server` URL |
| 5 | `connect/security/license.xml` | `security/license.xml` (12 lines) | `ir.model.access` for `oduist.license` (admin only) |
| 6 | `connect/static/src/components/license_banner/license_banner.js` | same path (63 lines) | OWL systray component |
| 7 | `connect/static/src/components/license_banner/license_banner.xml` | same path (12 lines) | QWeb template |
| 8 | `connect/static/src/components/license_banner/license_banner.scss` | same path (63 lines) | Banner styles |

### 2.2 Files to Modify

| # | File (target) | Change |
|---|---------------|--------|
| 1 | `connect/models/__init__.py` | Add `from . import license` and `from . import ir_module_module` |
| 2 | `connect/__init__.py` | Add `post_init_hook` function (license status update on install) |
| 3 | `connect/__manifest__.py` | Add `data/license.xml`, `security/license.xml`, `views/license.xml` to `data`; add `license_banner/*` to `assets`; add `'post_init_hook': 'post_init_hook'`; add `pyjwt` to `external_dependencies.python` |
| 4 | `connect/models/settings.py` | Add `ODUIST_MODULES` import and `ODUIST_MODULES.append('connect')` |
| 5 | `requirements.txt` | Add `pyjwt` |

### 2.3 License Enforcement Call Sites

These models in the new codebase need `check_license()` calls added at the same enforcement points as the old codebase:

| # | Model file (target) | Method(s) | Enforcement type |
|---|---------------------|-----------|-----------------|
| 1 | `connect/models/call.py` | Incoming call processing (after `on_call_status`) | `check_license('connect', silent=True)` — returns False silently |
| 2 | `connect/models/call.py` | Outbound call initiation (click-to-call) | `check_license('connect', silent=False)` — raises ValidationError |
| 3 | `connect/models/message.py` | `receive()` — incoming SMS | `check_license('connect', silent=True)` |
| 4 | `connect/models/message.py` | `send()` — outgoing SMS | `check_license('connect', silent=False)` |
| 5 | `connect/models/number.py` | `render()` — IVR/callflow rendering | `check_license('connect', silent=True)` — returns empty on expired |

**Note**: `domain.py` and `whatsapp_sender.py` exist only in the old monolithic module (Twilio-specific). Their equivalents in `connect_ng` are:
- `domain.py` → lives in `connect_twilio` (porting check_license there is a separate task)
- `whatsapp_sender.py` → lives in `connect_twilio` (same)

---

## 3. Detailed Porting Steps

### Step 1: Add Python Dependency

Add `pyjwt` to `requirements.txt` and to `__manifest__.py` `external_dependencies`:

```python
'external_dependencies': {
    'python': ['phonenumbers', 'jinja2', 'openai', 'jwt'],
},
```

### Step 2: Create `connect/models/license.py`

Copy from source verbatim. Key elements to preserve:
- `PUBLIC_KEY_PARAM = "oduist_license.public_key"`
- `ODUIST_MODULES = []` — mutable list, populated by each module's `settings.py`
- `rpc()` helper function for JSON-RPC calls to license server
- `OduistLicense` model (`_name = "oduist.license"`) with:
  - Fields: `instance_uid`, `license_token`, `registration_number`, `subscribe_email`, `subscribe_to_security_alerts`, `subscribe_to_onboarding`, `subscribe_to_updates`, `oduist_modules` (M2M computed), `all_modules_purchased` (computed)
  - `create()` override — auto-generates UUID `instance_uid`
  - `write()` override — triggers `update_license_status` on subscription field changes
  - `get_param()` / `set_param()` — single-record parameter accessor pattern
  - `open_license_form()` — returns action dict
  - `_get_license_token()` / `_get_public_key()` — token/key retrieval
  - `validate_token()` — JWT RS256 validation with instance_uid matching
  - `is_trial_valid()` — 30-day trial based on module `create_date`
  - `get_license_status()` — returns status dict (`demo`/`production`/`trial_active`/`trial_expired`)
  - `get_oduist_license_banner()` — priority-based banner info for systray
  - `check_license()` — main enforcement entry point (silent vs raising)
  - `update_license_status()` — RPC to license server, updates token/key/pricing
  - `buy_all_licenses()` / `buy_licenses()` — purchase flow via license server

**No changes needed** — the model is provider-agnostic, no Twilio/FreeSWITCH imports.

### Step 3: Create `connect/models/ir_module_module.py`

Copy from source verbatim. Extends `ir.module.module` with:
- `oduist_license_status` (Char, computed) — display string
- `oduist_module_purchased` (Boolean, computed) — purchase flag
- `oduist_module_price` (Char, readonly) — price from license server
- `oduist_module_show_price` (Char, computed) — conditional display
- `_compute_oduist_license_status()` — calls `License.get_license_status()`
- `buy_oduist_license()` — per-module purchase action

### Step 4: Create Data/Security/View XML Files

#### `connect/data/license.xml`
Copy verbatim. Sets `ir.config_parameter` key `oduist_license_server` = `https://license.oduist.com`.

#### `connect/security/license.xml`
Copy verbatim. Grants full CRUD to `base.group_system` on `oduist.license`.

#### `connect/views/license.xml`
Copy verbatim. Contains:
- Server action `oduist_license_action` → calls `model.open_license_form()`
- Menu item under `connect.connect_settings_menu`, visible to `connect.group_connect_admin`
- Form view `oduist_license_form` with registration number, subscription toggles, email field, update/buy buttons, modules list

**Verify**: menu parent `connect.connect_settings_menu` exists in `connect_ng`. If the XML ID differs, update the `parent` attribute accordingly.

### Step 5: Create Frontend License Banner

Copy all 3 files verbatim into `connect/static/src/components/license_banner/`:
- `license_banner.js` — OWL component registered as systray item
- `license_banner.xml` — QWeb template with info/warning/danger states
- `license_banner.scss` — Styles with pulse animations for warning/danger

### Step 6: Update `connect/models/__init__.py`

Add two imports:
```python
from . import ir_module_module
from . import license
```

### Step 7: Update `connect/__init__.py`

Add post-init hook:
```python
import logging
from odoo import fields, api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    try:
        module = env['ir.module.module'].search([('name', '=', 'connect')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
```

**Note**: The old code supports Odoo 15/16 dual-signature (`cr, registry` vs `env`). Since `connect_ng` targets Odoo 19 only, use the single `env` argument form.

### Step 8: Update `connect/__manifest__.py`

Add to `data` list (order matters — data before security before views):
```python
'data': [
    # ... existing entries ...
    # License
    'data/license.xml',          # after other data files
    'security/license.xml',      # after other security files
    'views/license.xml',         # after other view files
],
```

Add post-init hook:
```python
'post_init_hook': 'post_init_hook',
```

Add `jwt` to external dependencies:
```python
'external_dependencies': {
    'python': ['phonenumbers', 'jinja2', 'openai', 'jwt'],
},
```

Add license banner assets — locate existing `assets` key or add:
```python
'assets': {
    'web.assets_backend': [
        '/connect/static/src/components/license_banner/*',
    ],
},
```

### Step 9: Register `connect` in `ODUIST_MODULES`

In `connect/models/settings.py`, add at module level (after imports):
```python
from odoo.addons.connect.models.license import ODUIST_MODULES
ODUIST_MODULES.append('connect')
```

### Step 10: Add License Enforcement to Business Models

Add `check_license` calls to existing methods in `connect_ng`:

#### `connect/models/call.py`
1. Find the incoming call processing method (equivalent of old `on_call_status` consumer). Add after channel creation:
   ```python
   if not self.env['oduist.license'].check_license('connect', silent=True):
       return False
   ```
2. Find the outbound call method (click-to-call). Add before call initiation:
   ```python
   self.env['oduist.license'].check_license('connect', silent=False)
   ```

#### `connect/models/message.py`
1. In `receive()` method, add at the top:
   ```python
   if not self.env['oduist.license'].check_license('connect', silent=True):
       return False
   ```
2. In `send()` method, add at the top:
   ```python
   self.env['oduist.license'].check_license('connect', silent=False)
   ```

#### `connect/models/number.py`
1. In `render()` method, add at the top:
   ```python
   if not self.env['oduist.license'].check_license('connect'):
       return ''
   ```

### Step 11: Update `requirements.txt`

Add `pyjwt` (the package name for `import jwt`):
```
pyjwt
```

---

## 4. Verification Checklist

- [ ] `oduist.license` model loads without errors
- [ ] License form opens from Settings → License menu
- [ ] `update_license_status` button makes RPC to license server
- [ ] `check_license` returns `True` during 30-day trial
- [ ] `check_license` returns `False` / raises after trial expiry
- [ ] License banner appears in systray for trial/expired states
- [ ] `buy_all_licenses` / `buy_oduist_license` open payment link
- [ ] `ir.module.module` shows license status columns in license form
- [ ] Post-init hook runs on module install
- [ ] `ODUIST_MODULES` list contains `'connect'` at runtime
- [ ] No Twilio/FreeSWITCH imports in any license code
- [ ] JWT validation works with RS256 public key

---

## 5. Out of Scope (Future Tasks)

These belong in separate porting tasks for `connect_twilio` and `connect_freeswitch`:

- `domain.py` → `check_license` in `route_call()` (Twilio SIP domain routing)
- `whatsapp_sender.py` → `check_license` in WhatsApp send (Twilio WhatsApp)
- Other modules' `ODUIST_MODULES.append()` calls (`connect_crm`, `connect_helpdesk`, `connect_website`, `connect_elevenlabs`, `connect_byoc`)
