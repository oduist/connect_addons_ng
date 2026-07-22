# Connect Domain Bridges (account / sale / hr / project) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four provider-agnostic call↔record bridges — `connect_account`, `connect_sale`, `connect_hr`, `connect_project` — that link a `connect.call` to an invoice / sale order / employee / task, exactly the way `connect_crm` links a call to a lead (ADR-046 Part 1, ODU-344).

**Architecture:** Each bridge is a small standalone module depending on `['connect', '<app>']`. It `_inherit`s `connect.call` to add ONE dedicated `Many2one` to the target record (never the shared `ref` slot as the source of truth), wires the core hooks (`process_call_event` to link by lookup, `register_call` + `_auto_create_*` where auto-create applies, `_get_ref`, `get_widget_fields`, a `@api.constrains('summary')` summary sync), and `_inherit`s the target model to add a `connect_calls` One2many + stored count + a smart button. `connect_crm` is the canonical reference — every bridge repeats its shape with per-module deltas.

**Tech Stack:** Odoo 19 addon (Python/XML), `oduflow` MCP for a live-mount test environment, `connect` core license/hook API (`oduist.license.check_license`, `connect.call.process_call_event`/`register_call`/`_get_ref`/`get_widget_fields`/`register_summary_to_rec`), `res.partner._normalize_phone`, `connect.settings.get_param`.

## Global Constraints

- **Target Odoo series: 19.0 only.** No `release.version_info` version-forks in `.py`. Python must stay byte-identical across series (18.0 backport touches only XML/migrations — ADR-039), so branch on `release.version_info[0]` ONLY where the existing core already does (none needed here).
- **Manifest:** `'version': '19.0.1.0.0'`, `'license': 'Other proprietary'`, `'category': 'Phone'`, `'application': False`, `'post_init_hook': 'post_init_hook'`. Author `'Oduist'`.
- **Bump the manifest version at most once** (each bridge is one release unit at `19.0.1.0.0`).
- **Commit messages:** `[connect_<app>] <subject>` (single-module) / `[misc] <subject>` (cross-cutting). Lowercase imperative, square brackets. NO `feat:`/`fix:`/`chore:` prefixes.
- **Comments in English only.**
- **Security default for new models:** none are added — bridges only `_inherit` existing models. Webhook write access to each target goes to `connect.group_webhook` via `security/webhook.xml` (read + create/write only where the bridge writes that record). NO broad create/write beyond what the bridge needs.
- **License gate:** every hook/button first calls `self.env['oduist.license'].check_license('connect_<app>', silent=True)` and returns/`super()`s on failure — capture must never break the host op.
- **Register each module in the license registry:** `ODUIST_MODULES.append('connect_<app>')` in `models/settings.py` (or the first imported model file if there is no settings model).
- **Tests are colocated** (`connect_<app>/tests/`, ADR-034), imported in `tests/__init__.py`, and follow the `connect_crm/tests/common.py` pattern.
- **Do NOT port these source anti-patterns (ADR-046 blacklist):** `update_reference()` + `if not res` chain; the `ref`/`model`/`res_id` triplet as the only link; unstored `*_calls_count`; dead `create(call_id)` hooks nobody feeds; `invalidate_model(flush=True)` (use `self.env.registry.clear_cache()`); `@tools.ormcache` on lookups; `release.version_info` forks; `self.env.cr.commit()`; `view_mode='tree,form'` (use `'list,form'`); stale manifest keys (`qweb`, `price`, `images`); over-broad ACLs; copy-paste class names (`AccountOrder`) and rule ids.

---

## Reference: the Shared Bridge Pattern (canonical = `connect_crm`)

Every task below **instantiates** this pattern. Read these reference files once; each task lists only its deltas.

- `connect_crm/models/call.py` — `_inherit connect.call`: dedicated M2O, `_get_ref`, `process_call_event`, `register_call`, `_auto_create_*`, `create_*_button`, `unlink_*`, `get_widget_fields`, `register_*_call_summary`.
- `connect_crm/models/crm_lead.py` — `_inherit` target: `connect_calls` One2many, stored `connect_calls_count` (`@api.depends('connect_calls')`), `phone_normalized`, `get_*_by_number`, `create()` reading `connect_call_id`.
- `connect_crm/models/settings.py` — `ODUIST_MODULES.append(...)`.
- `connect_crm/__init__.py` — `post_init_hook(env)`.
- `connect_crm/__manifest__.py`, `connect_crm/security/webhook.xml`, `connect_crm/views/{call_views,crm_lead_views}.xml`, `connect_crm/tests/*`.

**Canonical `_get_ref` override** (repeat verbatim, swap `<m2o>`/`<target_model>`):
```python
def _get_ref(self):
    for rec in self:
        if rec.<m2o>:
            rec.ref = '<target_model>,{}'.format(rec.<m2o>.id)
        else:
            super(<Class>, rec)._get_ref()
```

**Canonical `connect.call` list/form view inheritance** (`views/call_views.xml`):
```xml
<record id="view_connect_call_tree_<app>" model="ir.ui.view">
    <field name="name">connect.call.tree.<app></field>
    <field name="model">connect.call</field>
    <field name="inherit_id" ref="connect.view_connect_call_tree"/>
    <field name="arch" type="xml">
        <field name="partner" position="after">
            <field name="<m2o>" optional="show"/>
        </field>
    </field>
</record>
<record id="view_connect_call_form_<app>" model="ir.ui.view">
    <field name="name">connect.call.form.<app></field>
    <field name="model">connect.call</field>
    <field name="inherit_id" ref="connect.view_connect_call_form"/>
    <field name="arch" type="xml">
        <button name="create_partner_button" position="after">
            <button string="<Label>" name="create_<app>_button" type="object"
                    class="oe_stat_button" icon="<icon>"/>
        </button>
        <notebook position="inside">
            <page name="<app>" string="<Label>">
                <group>
                    <group><field name="<m2o>"/></group>
                    <group>
                        <button name="unlink_<app>" type="object" string="Unlink"
                                invisible="not <m2o>"/>
                    </group>
                </group>
            </page>
        </notebook>
    </field>
</record>
```
(Bridges without a create-from-call button — `connect_account`, `connect_hr` — omit the `<button ... position="after">` block.)

**Canonical smart button on the target form** (`views/<record>_views.xml`):
```xml
<record id="connect_calls_<app>_action" model="ir.actions.act_window">
    <field name="name">Calls</field>
    <field name="res_model">connect.call</field>
    <field name="view_mode">list,form</field>
    <field name="domain">[('<m2o>', '=', active_id)]</field>
</record>
<record id="view_<record>_form_connect_<app>" model="ir.ui.view">
    <field name="name">connect_<app>.<record>.form</field>
    <field name="model"><target_model></field>
    <field name="inherit_id" ref="<core_form_ref>"/>
    <field name="arch" type="xml">
        <xpath expr="<button_box_xpath>" position="inside">
            <button name="%(connect_calls_<app>_action)d" type="action"
                    class="oe_stat_button" icon="fa-phone">
                <field name="connect_calls_count" string="Calls" widget="statinfo"/>
            </button>
        </xpath>
    </field>
</record>
```

**Canonical `post_init_hook`** (`__init__.py`, swap the module name):
```python
from . import models
import logging
from odoo import fields
_logger = logging.getLogger(__name__)

def post_init_hook(env):
    try:
        module = env['ir.module.module'].search([('name', '=', 'connect_<app>')], limit=1)
        if module:
            module.write({'create_date': fields.Datetime.now()})
        env['oduist.license'].update_license_status(raise_exc=False)
    except Exception as e:
        _logger.error('Error in post_init_hook: %s', str(e))
```

**Per-bridge parameter table** (fill the pattern with these):

| Bridge | depends | target model | link M2O | `ref` label | lookup strategy | auto-create | create button | core form ref / button_box xpath |
|---|---|---|---|---|---|---|---|---|
| connect_hr | `['connect','hr']` | `hr.employee` | `employee` | `Employee` | by number (employee `work_phone`/`mobile_phone`) | no | no | `hr.view_employee_form` / `//div[@name='button_box']` |
| connect_sale | `['connect','sale']` | `sale.order` | `sale_order` | `Sale Order` | by partner (open orders) | no | yes (`create_sale_order_button`) | `sale.view_order_form` / `//div[@name='button_box']` |
| connect_account | `['connect','account']` | `account.move` | `invoice` | `Invoice` | by partner (posted, unpaid, `out_invoice`) | no | no | `account.view_move_form` / `//div[@name='button_box']` |
| connect_project | `['connect','project']` | `project.task` (+`project.project`) | `task` (+`project`) | `Task`/`Project` | by partner (open task, else project) | no | yes (`create_task_button`) | `project.view_task_form2` / `//div[@name='button_box']` |

---

### Task 1: `connect_hr` — link calls to employees (lookup by number)

Closest to `connect_crm`: employees carry phone numbers, so calls link by number. The source `asterisk_plus_hr` was non-functional (unstored count, no lookup, `hr.employee.public` half-wired, dead view, misspelled `hr_empoloyee.py`) — implement fresh per the pattern. **Do not** include `hr.employee.public` in the `ref` selection (avoids the dead public view).

**Files:**
- Create: `connect_hr/__init__.py`, `connect_hr/__manifest__.py`
- Create: `connect_hr/models/__init__.py`, `connect_hr/models/call.py`, `connect_hr/models/hr_employee.py`, `connect_hr/models/settings.py`
- Create: `connect_hr/security/webhook.xml`
- Create: `connect_hr/views/call_views.xml`, `connect_hr/views/hr_employee_views.xml`
- Create: `connect_hr/static/description/icon.png`
- Test: `connect_hr/tests/__init__.py`, `connect_hr/tests/common.py`, `connect_hr/tests/test_employee_lookup.py`, `connect_hr/tests/test_process_event.py`

**Interfaces:**
- Consumes: core `connect.call` hooks (`process_call_event`, `_get_ref`, `get_widget_fields`), `res.partner._normalize_phone`, `oduist.license.check_license`.
- Produces: `connect.call.employee` (M2O), `hr.employee.connect_calls`/`connect_calls_count`/`phone_normalized`/`mobile_normalized`/`get_employee_by_number(number, country=None)`.

- [ ] **Step 1: Scaffold the module skeleton**

Create `connect_hr/__init__.py` (canonical `post_init_hook`, module `connect_hr`), `connect_hr/models/__init__.py`:
```python
from . import settings
from . import call
from . import hr_employee
```
Create `connect_hr/__manifest__.py`:
```python
{
    'name': 'Oduist Connect HR',
    'version': '19.0.1.0.0',
    'category': 'Phone',
    'summary': 'HR integration for Oduist Connect',
    'author': 'Oduist',
    'depends': ['connect', 'hr'],
    'data': [
        'security/webhook.xml',
        'views/hr_employee_views.xml',
        'views/call_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'Other proprietary',
}
```
Create `connect_hr/models/settings.py`:
```python
from odoo import models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_hr')


class ConnectHrSettings(models.Model):
    _inherit = 'connect.settings'
```

- [ ] **Step 2: Write the target-model extension `hr_employee.py`**

```python
import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug, MAX_EXTEN_LEN
from odoo.addons.connect.models.res_partner import strip_number

logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    connect_calls = fields.One2many('connect.call', 'employee')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    phone_normalized = fields.Char(
        compute='_get_phone_normalized', index=True, store=True,
    )
    mobile_normalized = fields.Char(
        compute='_get_phone_normalized', index=True, store=True,
    )

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('employee', '=', rec.id)],
            )

    @api.depends('work_phone', 'mobile_phone')
    def _get_phone_normalized(self):
        for rec in self:
            rec.phone_normalized = (
                self.env['res.partner']._normalize_phone(rec.work_phone)
                if rec.work_phone else False
            )
            rec.mobile_normalized = (
                self.env['res.partner']._normalize_phone(rec.mobile_phone)
                if rec.mobile_phone else False
            )

    def _search_employee_by_number(self, number):
        found = self.env['hr.employee'].sudo().search(
            ['|', ('phone_normalized', '=', number), ('mobile_normalized', '=', number)],
            order='id desc',
        )
        debug(self, 'Number {} belongs to employees: {}'.format(number, found.mapped('id')))
        return found[:1]

    def get_employee_by_number(self, number, country=None):
        number = strip_number(number)
        if not number or len(number) < MAX_EXTEN_LEN:
            return self.env['hr.employee']
        employee = self._search_employee_by_number('+{}'.format(number))
        if employee:
            return employee
        employee = self._search_employee_by_number(number)
        if employee:
            return employee
        return self.env['hr.employee']
```

- [ ] **Step 3: Write the `connect.call` bridge `call.py`**

```python
import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class HrCall(models.Model):
    _inherit = 'connect.call'

    employee = fields.Many2one('hr.employee', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[('hr.employee', 'Employee')])

    def _get_ref(self):
        for rec in self:
            if rec.employee:
                rec.ref = 'hr.employee,{}'.format(rec.employee.id)
            else:
                super(HrCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_hr', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.employee:
                number = call.caller if call.direction == 'incoming' else call.called
                employee = self.env['hr.employee'].get_employee_by_number(number)
                if employee:
                    debug(self, 'Call {} assign employee <{}> "{}"'.format(
                        call.id, employee.id, employee.name))
                    call.employee = employee
        except Exception:
            logger.exception('HR process_call_event error:')
        return call_id

    def unlink_employee(self):
        self.ensure_one()
        self.employee = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('employee')
        return fields

    @api.constrains('summary')
    def register_hr_employee_call_summary(self):
        if not self.env['oduist.license'].check_license('connect_hr', silent=True):
            return False
        if not self.env['connect.settings'].sudo().get_param('register_summary'):
            return
        reload_view = False
        for rec in self:
            if rec.employee and rec.summary:
                self.register_summary_to_rec(rec.employee, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('hr.employee')
```

- [ ] **Step 4: Write `security/webhook.xml`** (read-only on `hr.employee` for the webhook group)

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="access_hr_employee_webhook" model="ir.model.access">
        <field name="name">hr.employee webhook</field>
        <field name="model_id" ref="hr.model_hr_employee"/>
        <field name="group_id" ref="connect.group_webhook"/>
        <field name="perm_read" eval="1"/>
        <field name="perm_create" eval="0"/>
        <field name="perm_write" eval="1"/>
        <field name="perm_unlink" eval="0"/>
    </record>
</odoo>
```
(`perm_write=1` so `process_call_event`, running as the webhook user, can set `call.employee` — the write is on `connect.call`, but the summary sync writes `hr.employee`; keep write, drop create/unlink.)

- [ ] **Step 5: Write the views**

`connect_hr/views/call_views.xml` — instantiate the canonical `connect.call` list/form pattern with `<app>=hr`, `<m2o>=employee`, `<Label>=Employee`, **omit** the create button (no create-from-call). `connect_hr/views/hr_employee_views.xml` — canonical smart button with `core_form_ref=hr.view_employee_form`, `button_box_xpath=//div[@name='button_box']`, plus a search-view extension exposing `work_phone`/`mobile_phone` (inherit `hr.view_employee_filter`).

- [ ] **Step 6: Write `tests/common.py` + `tests/__init__.py`**

Mirror `connect_crm/tests/common.py`: a `TransactionCase` subclass exposing `Employee = env['hr.employee']`, `Call = env['connect.call']`, `Settings`, a `webhook_user = env.ref('connect.user_connect_webhook')`, `_create_call(**vals)` (defaults `caller`/`called`/`direction='incoming'`/`status='completed'`, `sudo().with_context(tracking_disable=True)`), and a `mock_license_check` contextmanager patching `oduist.license.check_license`. `tests/__init__.py` imports `test_employee_lookup`, `test_process_event`.

- [ ] **Step 7: Write the failing tests**

`connect_hr/tests/test_employee_lookup.py`:
```python
from .common import ConnectHrTestCommon


class TestEmployeeLookup(ConnectHrTestCommon):

    def test_lookup_by_work_phone(self):
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        self.env.flush_all()
        found = self.Employee.get_employee_by_number('380671234567')
        self.assertEqual(found, emp)

    def test_lookup_by_mobile(self):
        emp = self.Employee.create({'name': 'Sue', 'mobile_phone': '+380509999999'})
        self.env.flush_all()
        self.assertEqual(self.Employee.get_employee_by_number('+380509999999'), emp)

    def test_lookup_unknown_returns_empty(self):
        self.assertFalse(self.Employee.get_employee_by_number('+380000000000'))
```

`connect_hr/tests/test_process_event.py`:
```python
from .common import ConnectHrTestCommon


class TestProcessEvent(ConnectHrTestCommon):

    def test_incoming_call_links_employee(self):
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        self.env.flush_all()
        call = self._create_call(caller='+380671234567', direction='incoming')
        with self.mock_license_check(True):
            call.employee = self.Employee.get_employee_by_number(call.caller)
        self.assertEqual(call.employee, emp)

    def test_get_ref_reflects_employee(self):
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        call = self._create_call()
        call.employee = emp
        self.assertEqual(call.ref, emp)
```

- [ ] **Step 8: Push, install, run tests**

```
git add connect_hr && git commit -m "[connect_hr] add HR call bridge (employee link, lookup by number)"
git push
```
Then (oduflow MCP, live-mount env): `pull_and_apply(install="connect_hr")`, read the response for ParseError/access errors; `run_odoo_tests connect_hr`.
Expected: installs clean; `test_employee_lookup` + `test_process_event` pass (0 failed).

- [ ] **Step 9: Add the icon and finalize**

Copy the shared icon: `cp .claude/skills/writing-odoo-module-description/icon.png connect_hr/static/description/icon.png`; add `'images': ['static/description/icon.png']` to the manifest. Commit `[connect_hr] add store icon`.

---

### Task 2: `connect_sale` — link calls to sale orders (lookup by partner)

Sale orders have no own phone, so linking is **by partner** (open orders only). Optional create-from-call button. Drop the source's dead `sale.order.create(call_id)` hook — the NG create hook reads `connect_call_id`.

**Files:**
- Create: `connect_sale/__init__.py`, `connect_sale/__manifest__.py`
- Create: `connect_sale/models/__init__.py`, `connect_sale/models/call.py`, `connect_sale/models/sale_order.py`, `connect_sale/models/settings.py`
- Create: `connect_sale/security/webhook.xml`
- Create: `connect_sale/views/call_views.xml`, `connect_sale/views/sale_order_views.xml`
- Create: `connect_sale/static/description/icon.png`
- Test: `connect_sale/tests/{__init__,common}.py`, `connect_sale/tests/test_order_lookup.py`, `connect_sale/tests/test_process_event.py`

**Interfaces:**
- Produces: `connect.call.sale_order` (M2O), `create_sale_order_button`, `unlink_sale_order`; `sale.order.connect_calls`/`connect_calls_count`/`get_order_by_partner(partner)`/`create()` reading `connect_call_id`.

- [ ] **Step 1: Scaffold** — as Task 1 with `connect_sale`, `depends ['connect', 'sale']`, manifest `data` = `['security/webhook.xml', 'views/sale_order_views.xml', 'views/call_views.xml']`. `models/__init__.py` imports `settings, call, sale_order`. `models/settings.py` appends `'connect_sale'` to `ODUIST_MODULES`.

- [ ] **Step 2: Target extension `sale_order.py`**

```python
import logging

from odoo import api, fields, models

logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    connect_calls = fields.One2many('connect.call', 'sale_order')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('sale_order', '=', rec.id)],
            )

    @api.model
    def get_order_by_partner(self, partner):
        if not partner:
            return self.env['sale.order']
        return self.env['sale.order'].sudo().search(
            [('partner_id', '=', partner.id), ('state', 'in', ('draft', 'sent', 'sale'))],
            order='id desc', limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if self.env.context.get('connect_call_id') and recs:
            call = self.env['connect.call'].sudo().browse(self.env.context['connect_call_id'])
            call.sale_order = recs[0]
        if recs:
            self.env.registry.clear_cache()
        return recs
```

- [ ] **Step 3: Bridge `call.py`** — instantiate the pattern (`<m2o>=sale_order`, target `sale.order`), with by-partner lookup and a create button:

```python
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class SaleCall(models.Model):
    _inherit = 'connect.call'

    sale_order = fields.Many2one('sale.order', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[('sale.order', 'Sale Order')])

    def _get_ref(self):
        for rec in self:
            if rec.sale_order:
                rec.ref = 'sale.order,{}'.format(rec.sale_order.id)
            else:
                super(SaleCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_sale', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.sale_order and call.partner:
                order = self.env['sale.order'].get_order_by_partner(call.partner)
                if order:
                    debug(self, 'Call {} assign order <{}> "{}"'.format(
                        call.id, order.id, order.name))
                    call.sale_order = order
        except Exception:
            logger.exception('Sale process_call_event error:')
        return call_id

    def create_sale_order_button(self):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect_sale', silent=True):
            raise ValidationError('Connect Sale license is not activated!')
        context = {'connect_call_id': self.id, 'default_partner_id': self.partner.id}
        if not self.sale_order and self.partner:
            order = self.env['sale.order'].get_order_by_partner(self.partner)
            if order:
                self.sudo().sale_order = order
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order.id if self.sale_order else False,
            'name': self.sale_order.name if self.sale_order else 'New Sale Order',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def unlink_sale_order(self):
        self.ensure_one()
        self.sale_order = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('sale_order')
        return fields

    @api.constrains('summary')
    def register_sale_order_call_summary(self):
        if not self.env['oduist.license'].check_license('connect_sale', silent=True):
            return False
        if not self.env['connect.settings'].sudo().get_param('register_summary'):
            return
        reload_view = False
        for rec in self:
            if rec.sale_order and rec.summary:
                self.register_summary_to_rec(rec.sale_order, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('sale.order')
```

- [ ] **Step 4: `security/webhook.xml`** — read+write on `sale.order` for `connect.group_webhook` (id `access_sale_order_webhook`, `sale.model_sale_order`, `perm_read=1 perm_write=1 perm_create=0 perm_unlink=0`).

- [ ] **Step 5: Views** — `call_views.xml`: canonical list/form with the create button (`create_sale_order_button`, icon `fa-shopping-cart`, label `Sale Order`). `sale_order_views.xml`: smart button (`sale.view_order_form`, `//div[@name='button_box']`), `partner_phone`/`partner_mobile` on the form, and a search-filter extension on `sale.sale_order_view_search_inherit_quotation`/`...sale` exposing partner phones.

- [ ] **Step 6: Tests** — `common.py` mirrors Task 1 with `Order = env['sale.order']` and a `_create_partner`. `test_order_lookup.py`: `get_order_by_partner` returns the newest open order and empty when partner has only cancelled orders. `test_process_event.py`: an incoming call whose `partner` has an open order gets `sale_order` set; `create()` with `connect_call_id` context back-links the call.

```python
# test_order_lookup.py
from .common import ConnectSaleTestCommon


class TestOrderLookup(ConnectSaleTestCommon):

    def test_returns_open_order(self):
        order = self.Order.create({'partner_id': self.partner.id})
        self.env.flush_all()
        self.assertEqual(self.Order.get_order_by_partner(self.partner), order)

    def test_no_partner_returns_empty(self):
        self.assertFalse(self.Order.get_order_by_partner(self.env['res.partner']))
```

- [ ] **Step 7: Push, install, test** — `[connect_sale] add sale order call bridge (partner link + create button)`, `pull_and_apply(install="connect_sale")`, `run_odoo_tests connect_sale`. Expected: clean install, tests pass.

- [ ] **Step 8: Icon + commit** — copy shared icon, add `'images'`, commit `[connect_sale] add store icon`.

---

### Task 3: `connect_account` — link calls to customer invoices (lookup by partner, bug-fixed)

Invoices have no own phone → link **by partner**. **Fix the source bug**: the source mixed `in_invoice`/`out_invoice` regardless of call direction. Link only **customer** invoices (`out_invoice`), posted and not fully paid. No auto-create, no create button (never create an invoice from a call). Give it a **real ACL** (the source had none, band-aided with `sudo()`), and a correctly-named class (not `AccountOrder`).

**Files:**
- Create: `connect_account/__init__.py`, `connect_account/__manifest__.py`
- Create: `connect_account/models/{__init__,call,account_move,settings}.py`
- Create: `connect_account/security/webhook.xml`
- Create: `connect_account/views/{call_views,account_move_views}.xml`
- Create: `connect_account/static/description/icon.png`
- Test: `connect_account/tests/{__init__,common}.py`, `connect_account/tests/test_invoice_lookup.py`, `connect_account/tests/test_process_event.py`

**Interfaces:**
- Produces: `connect.call.invoice` (M2O to `account.move`); `account.move.connect_calls`/`connect_calls_count`/`get_invoice_by_partner(partner)`.

- [ ] **Step 1: Scaffold** — `connect_account`, `depends ['connect', 'account']`, `data = ['security/webhook.xml', 'views/account_move_views.xml', 'views/call_views.xml']`, `models/__init__.py` → `settings, call, account_move`, settings appends `'connect_account'`.

- [ ] **Step 2: Target extension `account_move.py`**

```python
import logging

from odoo import api, fields, models

logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    connect_calls = fields.One2many('connect.call', 'invoice')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('invoice', '=', rec.id)],
            )

    @api.model
    def get_invoice_by_partner(self, partner):
        if not partner:
            return self.env['account.move']
        return self.env['account.move'].sudo().search(
            [
                ('partner_id', '=', partner.id),
                ('state', '=', 'posted'),
                ('move_type', '=', 'out_invoice'),
                ('payment_state', '!=', 'paid'),
            ],
            order='invoice_date desc, id desc', limit=1,
        )
```

- [ ] **Step 3: Bridge `call.py`** — instantiate the pattern (`<m2o>=invoice`, target `account.move`), by-partner lookup, NO create button, NO auto-create:

```python
import logging

from odoo import api, fields, models

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class AccountCall(models.Model):
    _inherit = 'connect.call'

    invoice = fields.Many2one('account.move', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[('account.move', 'Invoice')])

    def _get_ref(self):
        for rec in self:
            if rec.invoice:
                rec.ref = 'account.move,{}'.format(rec.invoice.id)
            else:
                super(AccountCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_account', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.invoice and call.partner:
                invoice = self.env['account.move'].get_invoice_by_partner(call.partner)
                if invoice:
                    debug(self, 'Call {} assign invoice <{}> "{}"'.format(
                        call.id, invoice.id, invoice.name))
                    call.invoice = invoice
        except Exception:
            logger.exception('Account process_call_event error:')
        return call_id

    def unlink_invoice(self):
        self.ensure_one()
        self.invoice = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('invoice')
        return fields

    @api.constrains('summary')
    def register_account_move_call_summary(self):
        if not self.env['oduist.license'].check_license('connect_account', silent=True):
            return False
        if not self.env['connect.settings'].sudo().get_param('register_summary'):
            return
        reload_view = False
        for rec in self:
            if rec.invoice and rec.summary:
                self.register_summary_to_rec(rec.invoice, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('account.move')
```

- [ ] **Step 4: `security/webhook.xml`** — read+write on `account.move` for `connect.group_webhook` (id `access_account_move_webhook`, `account.model_account_move`, `perm_read=1 perm_write=1 perm_create=0 perm_unlink=0`).

- [ ] **Step 5: Views** — `call_views.xml`: canonical list/form, **no** create button. `account_move_views.xml`: smart button on `account.view_move_form` at `//div[@name='button_box']`, `partner_phone`/`partner_mobile` on the form, search filter on `account.view_account_invoice_filter` exposing partner phones.

- [ ] **Step 6: Tests** — `test_invoice_lookup.py`: `get_invoice_by_partner` returns a posted unpaid `out_invoice`, and empty for a `paid` invoice or an `in_invoice` (vendor bill) — the bug-fix guard. `test_process_event.py`: an incoming call whose partner has such an invoice gets `invoice` set.

```python
# test_invoice_lookup.py
from .common import ConnectAccountTestCommon


class TestInvoiceLookup(ConnectAccountTestCommon):

    def test_vendor_bill_is_ignored(self):
        self._post_invoice(move_type='in_invoice')  # vendor bill for self.partner
        self.assertFalse(self.Move.get_invoice_by_partner(self.partner))

    def test_customer_unpaid_invoice_found(self):
        inv = self._post_invoice(move_type='out_invoice')
        self.assertEqual(self.Move.get_invoice_by_partner(self.partner), inv)
```
`common.py` provides `_post_invoice(move_type)` creating a one-line invoice for `self.partner` and posting it (`Move.create({...}).action_post()`), plus `Move = env['account.move']`.

- [ ] **Step 7: Push, install, test** — `[connect_account] add invoice call bridge (partner link, out_invoice only)`, `pull_and_apply(install="connect_account")`, `run_odoo_tests connect_account`. Expected: clean, tests pass.

- [ ] **Step 8: Icon + commit** — shared icon, `'images'`, `[connect_account] add store icon`.

---

### Task 4: `connect_project` — link calls to tasks/projects + recorded-calls page

Two targets (`project.task` primary, `project.project`), **by-partner** lookup (open task first, else project), a `create_task_button`, and a `connect.recording` extension giving each task/project a **Recorded Calls** page. Drop the source's dead `project.create(call_id)` hook; keep the task-side back-link via `connect_call_id`.

**Files:**
- Create: `connect_project/__init__.py`, `connect_project/__manifest__.py`
- Create: `connect_project/models/{__init__,call,project,task,recording,settings}.py`
- Create: `connect_project/security/webhook.xml`
- Create: `connect_project/views/{call_views,project_views,task_views}.xml`
- Create: `connect_project/static/description/icon.png`
- Test: `connect_project/tests/{__init__,common}.py`, `connect_project/tests/test_lookup.py`, `connect_project/tests/test_recording_link.py`

**Interfaces:**
- Produces: `connect.call.task`/`connect.call.project` (M2O), `create_task_button`, `unlink_task`; `project.task`/`project.project` `connect_calls`/`connect_calls_count`/`recorded_calls`; `connect.recording.task`/`connect.recording.project`.

- [ ] **Step 1: Scaffold** — `connect_project`, `depends ['connect', 'project']`, `data = ['security/webhook.xml', 'views/project_views.xml', 'views/task_views.xml', 'views/call_views.xml']`, `models/__init__.py` → `settings, call, project, task, recording`, settings appends `'connect_project'`.

- [ ] **Step 2: Target extensions `project.py` and `task.py`**

`project.py`:
```python
from odoo import api, fields, models


class Project(models.Model):
    _inherit = 'project.project'

    connect_calls = fields.One2many('connect.call', 'project')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    recorded_calls = fields.One2many('connect.recording', 'project')
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('project', '=', rec.id)],
            )
```
`task.py` (same shape, `_inherit='project.task'`, count domain `('task', '=', rec.id)`, `recorded_calls` One2many on `'task'`, plus the `connect_call_id` back-link in `create`):
```python
from odoo import api, fields, models


class Task(models.Model):
    _inherit = 'project.task'

    connect_calls = fields.One2many('connect.call', 'task')
    connect_calls_count = fields.Integer(
        compute='_get_connect_calls_count', string='Calls', store=True,
    )
    recorded_calls = fields.One2many('connect.recording', 'task')
    partner_phone = fields.Char(related='partner_id.phone')
    partner_mobile = fields.Char(related='partner_id.mobile')

    @api.depends('connect_calls')
    def _get_connect_calls_count(self):
        for rec in self:
            rec.connect_calls_count = self.env['connect.call'].search_count(
                [('task', '=', rec.id)],
            )

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if self.env.context.get('connect_call_id') and recs:
            call = self.env['connect.call'].sudo().browse(self.env.context['connect_call_id'])
            call.task = recs[0]
        if recs:
            self.env.registry.clear_cache()
        return recs
```

- [ ] **Step 3: `recording.py`** — add `task`/`project` M2O and map them on create from the call's link:
```python
from odoo import api, fields, models


class Recording(models.Model):
    _inherit = 'connect.recording'

    task = fields.Many2one('project.task', ondelete='set null', readonly=True)
    project = fields.Many2one('project.project', ondelete='set null', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.call.task:
                rec.task = rec.call.task
            elif rec.call.project:
                rec.project = rec.call.project
        return recs
```

- [ ] **Step 4: Bridge `call.py`** — two M2Os, by-partner lookup (task, else project), `create_task_button`:
```python
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class ProjectCall(models.Model):
    _inherit = 'connect.call'

    task = fields.Many2one('project.task', ondelete='set null', tracking=True)
    project = fields.Many2one('project.project', ondelete='set null', tracking=True)
    ref = fields.Reference(selection_add=[
        ('project.task', 'Task'), ('project.project', 'Project')])

    def _get_ref(self):
        for rec in self:
            if rec.task:
                rec.ref = 'project.task,{}'.format(rec.task.id)
            elif rec.project:
                rec.ref = 'project.project,{}'.format(rec.project.id)
            else:
                super(ProjectCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license('connect_project', silent=True):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.task and not call.project and call.partner:
                task = self.env['project.task'].sudo().search(
                    [('partner_id', '=', call.partner.id),
                     ('stage_id.fold', '=', False)], order='id desc', limit=1)
                if task:
                    call.task = task
                else:
                    project = self.env['project.project'].sudo().search(
                        [('partner_id', '=', call.partner.id)], order='id desc', limit=1)
                    if project:
                        call.project = project
        except Exception:
            logger.exception('Project process_call_event error:')
        return call_id

    def create_task_button(self):
        self.ensure_one()
        if not self.env['oduist.license'].check_license('connect_project', silent=True):
            raise ValidationError('Connect Project license is not activated!')
        context = {
            'connect_call_id': self.id,
            'default_partner_id': self.partner.id,
            'default_name': 'Call from {}'.format(self.partner.name or self.caller),
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': self.task.id if self.task else False,
            'name': self.task.name if self.task else 'New Task',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def unlink_task(self):
        self.ensure_one()
        self.task = False
        self.project = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('task')
        fields.append('project')
        return fields

    @api.constrains('summary')
    def register_project_call_summary(self):
        if not self.env['oduist.license'].check_license('connect_project', silent=True):
            return False
        if not self.env['connect.settings'].sudo().get_param('register_summary'):
            return
        reload_view = False
        for rec in self:
            target = rec.task or rec.project
            if target and rec.summary:
                self.register_summary_to_rec(target, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('project.task')
```

- [ ] **Step 5: `security/webhook.xml`** — read+write on `project.task` and `project.project` for `connect.group_webhook` (two `ir.model.access` rows, `project.model_project_task`/`project.model_project_project`, `perm_read=1 perm_write=1 perm_create=1 perm_unlink=0` on task since the button creates tasks; project read+write only).

- [ ] **Step 6: Views** — `call_views.xml`: canonical list/form with the create button (`create_task_button`, icon `fa-tasks`, label `Task`), notebook page shows both `task` and `project`. `task_views.xml`/`project_views.xml`: smart button (`project.view_task_form2` / `project.edit_project`) + a **Recorded Calls** notebook page listing `recorded_calls` (fields `start_time`, `caller_number`, `called_number`, `recording_widget`) + phone fields.

- [ ] **Step 7: Tests** — `test_lookup.py`: an incoming call whose partner owns an open task links `task` (not `project`); when only a project matches, links `project`. `test_recording_link.py`: creating a `connect.recording` whose `call.task` is set copies `task` onto the recording and it shows up in `task.recorded_calls`.

```python
# test_recording_link.py
from .common import ConnectProjectTestCommon


class TestRecordingLink(ConnectProjectTestCommon):

    def test_recording_inherits_task_from_call(self):
        task = self.Task.create({'name': 'T', 'partner_id': self.partner.id})
        call = self._create_call(partner=self.partner.id)
        call.task = task
        rec = self.env['connect.recording'].sudo().create({'call': call.id})
        self.assertEqual(rec.task, task)
        self.assertIn(rec, task.recorded_calls)
```

- [ ] **Step 8: Push, install, test** — `[connect_project] add task/project call bridge + recorded calls`, `pull_and_apply(install="connect_project")`, `run_odoo_tests connect_project`. Expected: clean, tests pass.

- [ ] **Step 9: Icon + commit** — shared icon, `'images'`, `[connect_project] add store icon`.

---

### Task 5: Specs, docs, AGENTS.md, and PR

**Files:**
- Create: `specs/connect_account.md`, `specs/connect_sale.md`, `specs/connect_hr.md`, `specs/connect_project.md`
- Modify: `AGENTS.md`, `mkdocs.yml`
- Create: `docs/user/domain-bridges.md` (or per-module) if UI-facing docs are warranted

- [ ] **Step 1: Write the four specs** — follow `specs/connect_crm.md`: Module Info, Overview, Models (the `connect.call` deltas + target extension), Security, Views, per-module lookup/auto-create behavior. Note each is provider-agnostic (works for every provider that populates `connect.call`).

- [ ] **Step 2: Update `AGENTS.md`** — add the four modules to the Modules list (each: "provider-agnostic <app> bridge — links `connect.call` to `<record>`; depends `connect` + `<app>`"), the dependency note, the `specs/` list, the Testing tree, and the `run_odoo_tests` list.

- [ ] **Step 3: Update `mkdocs.yml`** — add any new doc pages to nav.

- [ ] **Step 4: Commit + open the PR** — `[misc] document connect_* domain bridges`; then `gh pr create --base 19.0 --head asterisk-plus-porting --title "Port asterisk_plus satellites: account/sale/hr/project bridges (ODU-344)"` with a body summarizing the four modules, the parity-audit finding (crm/helpdesk/phone already at parity), and test evidence. End the body with the Claude Code footer. Do NOT push to `19.0` (branch-protected).

---

## Self-Review Notes

- **Spec coverage (ADR-046 Part 1):** account/sale/hr/project each map to Tasks 1–4; the shared pattern (dedicated M2O, `process_call_event`/`register_call`/`_get_ref`/`get_widget_fields`, stored counts, no `update_reference` chain) is enforced by the Reference section + per-task code. Vendor-flavour (gs/yeastar), callgroup, website are explicitly OUT of this plan (separate ADR-046 Parts 2/3 cycles).
- **Blacklist honored:** no `update_reference`, no unstored counts, no `invalidate_model(flush=True)`, no `@tools.ormcache`, no version-forks, `list,form` view mode, real ACLs, unique class/rule names.
- **Placeholder scan:** model code is given in full per task; views/tests reference the shared pattern with explicit per-module anchors and concrete key test bodies. The connect_account bug-fix (customer `out_invoice` only) and the hr from-scratch rebuild are called out with tests that lock the corrected behavior.
- **Type consistency:** link fields (`employee`/`sale_order`/`invoice`/`task`+`project`), lookup methods (`get_employee_by_number`/`get_order_by_partner`/`get_invoice_by_partner`), and button names (`create_sale_order_button`/`create_task_button`, `unlink_*`) are used consistently across each task's model, views, and tests.
