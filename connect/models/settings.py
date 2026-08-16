import inspect
import json
import logging
import os
import re
import string
import random

import httpx
import openai
from odoo import fields, models, api, release
from odoo.exceptions import ValidationError, UserError

from odoo.addons.connect.models.license import ODUIST_MODULES
ODUIST_MODULES.append('connect')


logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4
PROTECTED_FIELDS = [
    "display_openai_api_key",
]


def debug(rec, message, level="info"):
    caller_module = inspect.stack()[1][3]
    if level == "info":
        fun = logger.info
    elif level == "warning":
        fun = logger.warning
        fun("++++++ {}: {}".format(caller_module, message))
    elif level == "error":
        fun = logger.error
        fun("++++++ {}: {}".format(caller_module, message))
    if rec.env["connect.settings"].sudo().get_param("debug_mode"):
        rec.env["connect.debug"].sudo().create(
            {
                "model": str(rec),
                "message": caller_module + ": " + message,
            }
        )
        if level == "info":
            fun("++++++ {}: {}".format(caller_module, message))


def format_connect_response(text):
    if not isinstance(text, str):
        text = str(text)
    symbol_pattern = re.compile(r"(\x08.)|\x08")
    text = symbol_pattern.sub("", text)
    color_pattern = re.compile(r"\x1b\[[\d;]+m")
    text = color_pattern.sub("", text)
    return text


def generate_password():
    characters = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
    ]
    characters += random.choices(string.ascii_letters + string.digits, k=20)
    random.shuffle(characters)
    return "".join(characters)


def strip_number(number):
    if not isinstance(number, str):
        return number
    pattern = r"[\s\(\)\-\+]"
    return re.sub(pattern, "", number).lstrip("0")


class Settings(models.Model):
    _name = "connect.settings"
    _description = "Settings"

    name = fields.Char(compute="_get_name")
    debug_mode = fields.Boolean()
    openai_api_key = fields.Char(groups="base.group_erp_manager")
    display_openai_api_key = fields.Char()
    number_search_operation = fields.Selection(
        [("=", "Equal"), ("like", "Like")], default="=", required=True
    )
    proxy_recordings = fields.Boolean(
        help="Re-stream recordings using Odoo user auth.", default=True
    )
    transcript_calls = fields.Boolean()
    transcript_provider = fields.Selection(
        selection=[('openai', 'Open AI')], default='openai', required=True
    )
    openai_summary_model = fields.Selection(
        selection=[
            ('gpt-5.4-mini', 'GPT-5.4 mini'),
            ('gpt-4o', 'GPT-4o'),
        ],
        default='gpt-5.4-mini',
        required=True,
    )
    summary_prompt = fields.Text(
        required=True, default="Summarise this phone call"
    )
    register_summary = fields.Boolean(
        default=True, help="Register summary at partner of reference chat."
    )
    instance_uid = fields.Char("Instance UID", compute="_get_instance_data")
    api_url = fields.Char("API URL", compute="_get_instance_data")
    api_fallback_url = fields.Char("API Fallback URL")
    web_base_url = fields.Char(compute="_get_instance_data", string="Odoo URL")
    call_duration_limit = fields.Integer(compute="_get_instance_data", string="Call Duration Limit (seconds)")

    def _get_instance_data(self):
        for rec in self:
            rec.instance_uid = (
                self.env["ir.config_parameter"].sudo().get_param("connect.instance_uid")
            )
            rec.api_url = (
                self.env["ir.config_parameter"].sudo().get_param("connect.api_url")
            )
            rec.web_base_url = (
                self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            )
            rec.call_duration_limit = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("connect.call_duration_limit", "7200")
            )

    @api.model
    def connect_notify(
        self, message, title="Connect", notify_uid=None, sticky=False, warning=False
    ):
        if not notify_uid:
            notify_uid = self.env.uid

        if release.version_info[0] < 15:
            self.env["bus.bus"].sendone(
                "connect_actions_{}".format(notify_uid),
                {
                    "action": "notify",
                    "message": message,
                    "title": title,
                    "sticky": sticky,
                    "warning": warning,
                },
            )
        else:
            self.env["bus.bus"]._sendone(
                "connect_actions_{}".format(notify_uid),
                "connect_notify",
                {
                    "message": message,
                    "title": title,
                    "sticky": sticky,
                    "warning": warning,
                },
            )

        return True

    @api.model
    def connect_reload_view(self, model):
        if release.version_info[0] < 15:
            msg = {
                "action": "reload_view",
                "model": model,
            }
            self.env["bus.bus"].sendone("connect_actions", json.dumps(msg))
        else:
            msg = {"model": model}
            self.env["bus.bus"]._sendone("connect_actions", "reload_view", msg)

    @api.model
    def set_defaults(self):
        api_url = self.get_param("api_url")
        if not api_url:
            web_base_url = (
                self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            )
            self.env["ir.config_parameter"].set_param("connect.api_url", web_base_url)
        installation_date = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("connect.installation_date")
        )
        if not installation_date:
            installation_date = fields.Datetime.now()
            self.env["ir.config_parameter"].set_param(
                "connect.installation_date", installation_date
            )

    @api.model
    def _get_name(self):
        for rec in self:
            rec.name = "General Settings"

    def open_settings_form(self, view_xmlid="connect.connect_settings_form", name="General Settings"):
        rec = self.search([])
        if not rec:
            rec = self.sudo().with_context(no_constrains=True).create({})
        else:
            rec = rec[0]
        return {
            "type": "ir.actions.act_window",
            "res_model": "connect.settings",
            "res_id": rec.id,
            "name": name,
            "view_mode": "form",
            "view_id": self.env.ref(view_xmlid).id,
            "target": "current",
        }

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        """Dispatch click-to-call to the telephony provider chosen on the
        connect.user (originate_provider). With a single provider module
        installed the choice is implicit. Provider modules override this
        method: handle the call when _get_originate_provider(user) returns
        their key, otherwise fall through to super().
        """
        raise UserError(
            'No telephony module can handle this call. Install a telephony '
            'module (Twilio, FreeSWITCH, Asterisk) and select a click-to-call '
            'provider on the Connect user.')

    @api.model
    def _get_originate_provider(self, user=None):
        """Resolve the provider key used to originate calls for the user."""
        odoo_user = user or self.env.user
        connect_user = self.env['connect.user'].sudo().search(
            [('user', '=', odoo_user.id)], limit=1)
        provider = connect_user.originate_provider
        if provider:
            return provider
        options = self.env['connect.user']._fields['originate_provider'].get_values(self.env)
        if len(options) == 1:
            return options[0]
        if not options:
            raise UserError('No telephony module is installed.')
        raise UserError(
            'Several telephony modules are installed. Select a click-to-call '
            'provider on the Connect user (Connect > Users).')

    @api.model
    def _get_message_provider(self, user=None):
        """Resolve the provider key used to send messages for the user."""
        odoo_user = user or self.env.user
        connect_user = self.env['connect.user'].sudo().search(
            [('user', '=', odoo_user.id)], limit=1)
        provider = connect_user.message_provider
        if provider:
            return provider
        options = self.env['connect.user']._fields['message_provider'].get_values(self.env)
        if len(options) == 1:
            return options[0]
        if not options:
            raise UserError('No messaging module is installed.')
        raise UserError(
            'Several messaging modules are installed. Select a messaging '
            'provider on the Connect user (Connect > Users).')

    @api.model
    def get_param(self, param, default=False):
        # Sudo-find the singleton so config reads do not require the caller to
        # hold connect.settings model access (the model is admin-only). Secret
        # parameters stay protected: a field carrying a ``groups=`` restriction
        # is only returned to a member of those groups (or to a sudo/internal
        # caller), never to a plain user reaching get_param over RPC.
        data = self.sudo().search([])
        if not data:
            data = self.sudo().with_context(no_constrains=True).create({})
        else:
            data = data[0]
        field = self._fields.get(param)
        if field is not None and field.groups and not self.env.su:
            allowed = any(
                self.env.user.has_group(group.strip())
                for group in field.groups.split(',')
                if group.strip() and not group.strip().startswith('!')
            )
            if not allowed:
                return default
        return getattr(data, param, default)

    @api.model
    def set_param(self, param, value):
        data = self.search([])
        if not data:
            data = self.sudo().with_context(no_constrains=True).create({})
        else:
            data = data[0]
        setattr(data, param, value)

    @api.model_create_multi
    def create(self, vals_list):
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
        return super(Settings, self).create(vals_list)

    def write(self, vals):
        if self.env.context.get("skip_protected_fields"):
            return super(Settings, self).write(vals)
        if not self.openai_api_key and vals.get("display_openai_api_key"):
            vals.update({"transcript_calls": True})
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace("display_", ""): vals.get(field_name),
                        field_name: "*" * len(vals.get(field_name)),
                    }
                )
        if changed_fields:
            self.with_context(skip_protected_fields=True).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()

    @api.model
    def get_openai_client(self):
        api_key = self.sudo().get_param('openai_api_key')
        if not api_key:
            return False
        # OPENAI_PROXY is both the switch and the proxy URL. The previous
        # code gated on OPENAI_PROXY but built the client from HTTPS_PROXY,
        # so setting only the documented OPENAI_PROXY produced proxy=None
        # and traffic egressed directly.
        openai_proxy = os.environ.get('OPENAI_PROXY')
        if openai_proxy:
            client = openai.OpenAI(
                api_key=api_key, http_client=httpx.Client(proxy=openai_proxy))
        else:
            client = openai.OpenAI(api_key=api_key)
        return client

    def check_api_url(self):
        message = None
        if re.match(r"^http://", self.get_param("api_url")):
            message = "Invalid api url! Please use HTTPS instead of HTTP to ensure a secure connection!"
        if re.match(
            r"(http|https)://(localhost|127\.0\.0\.\d)(:\d+)?",
            self.get_param("api_url"),
        ):
            message = "Invalid api url! Localhost is not allowed! Please use a valid and secure domain!"
        if message:
            logger.warning(message)
        return message

    def reformat_numbers_button(self):
        for rec in self.env["res.partner"].search([]):
            rec.phone = rec._normalize_phone(rec.phone)
            rec.mobile = rec._normalize_phone(rec.mobile)

    @api.onchange("transcript_calls")
    def _require_openai_key(self):
        if not self.sudo().get_param("openai_api_key"):
            raise ValidationError("You must set OpenAI key first!")

    def action_open_system_parameters(self):
        if release.version_info[0] >= 18:
            view_mode = "list,form"
        else:
            view_mode = "tree,form"
        return {
            "type": "ir.actions.act_window",
            "name": "System Parameters",
            "res_model": "ir.config_parameter",
            "view_mode": view_mode,
            "target": "current",
            "context": {"search_default_key": "connect.api_url"},
        }
