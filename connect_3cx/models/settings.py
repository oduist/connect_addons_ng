# -*- coding: utf-8 -*-
import logging
import re
import secrets
from string import Template
from urllib.parse import quote

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import file_open

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import PROTECTED_FIELDS

ODUIST_MODULES.append('connect_3cx')

# Mask the webhook API key the same way the core module masks openai_api_key.
if "display_threecx_api_key" not in PROTECTED_FIELDS:
    PROTECTED_FIELDS.append("display_threecx_api_key")

logger = logging.getLogger(__name__)

THREECX_TOKEN_MIN_LEN = 24
THREECX_TOKEN_ALLOWED_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)


class Settings(models.Model):
    _inherit = "connect.settings"

    threecx_enabled = fields.Boolean(
        string="3CX Enabled",
        default=False,
        help="Enable the 3CX integration (webhooks, click-to-call).",
    )
    threecx_pbx_url = fields.Char(
        string="PBX URL",
        help="Base URL of the 3CX PBX web client, e.g. "
             "https://mycompany.3cx.eu. Used to build the click-to-call "
             "dial URL (/webclient/#/call?phone=...).",
    )
    threecx_api_key = fields.Char(
        string="API Key (stored)",
        groups="connect.group_admin",
    )
    display_threecx_api_key = fields.Char(
        string="API Key",
        help="Shared secret the 3CX server sends with every webhook "
             "request (X-Connect-Api-Key header). It is embedded into the "
             "generated CRM template; regenerate it with the button and "
             "re-upload the template to rotate. The value is masked back "
             "to **** after saving. Visible only to administrators.",
    )
    # Status stamps (written by the webhook controllers).
    threecx_last_lookup = fields.Datetime(
        string="Last Contact Lookup", readonly=True)
    threecx_last_journal = fields.Datetime(
        string="Last Call Journal", readonly=True)

    @api.model
    def _validate_threecx_api_key(self, value):
        """Raise ValidationError on weak / malformed API key."""
        if value in (False, None):
            return
        value = value.strip()
        if not value:
            return
        if len(value) < THREECX_TOKEN_MIN_LEN:
            raise ValidationError(
                "API Key must be at least {} characters long.".format(
                    THREECX_TOKEN_MIN_LEN
                )
            )
        bad = sorted({c for c in value if c not in THREECX_TOKEN_ALLOWED_CHARS})
        if bad:
            raise ValidationError(
                "API Key can only contain letters, digits, '_' and '-'; "
                "remove: {}".format(" ".join(bad))
            )

    def write(self, vals):
        # The core settings.write() does a second-pass write under the
        # 'skip_protected_fields' context to replace the displayed
        # secret with asterisks. Skip our validation in that pass so we
        # don't reject the masked value.
        if not self.env.context.get("skip_protected_fields"):
            if "display_threecx_api_key" in vals:
                self._validate_threecx_api_key(
                    vals["display_threecx_api_key"]
                )
        return super().write(vals)

    def threecx_generate_api_key(self):
        """Settings form button: generate a fresh webhook API key."""
        self.ensure_one()
        # Route through the display field so the core protected-fields
        # flow copies it to threecx_api_key and masks the display value.
        self.write({"display_threecx_api_key": secrets.token_urlsafe(24)})
        self.env["connect.settings"].connect_notify(
            "New 3CX API key generated. Download the CRM template again "
            "and re-upload it to 3CX to apply the new key.",
            notify_uid=self.env.user.id)

    @api.model
    def threecx_get_crm_template(self):
        """Render the 3CX server-side CRM template XML for this instance.

        The template ships as a module resource with $odoo_url / $api_key
        placeholders; the instance URL and the shared webhook API key are
        substituted at download time so the admin can upload the file to
        the 3CX Admin Console as-is.
        """
        get_param = self.sudo().get_param
        api_key = get_param("threecx_api_key")
        if not api_key:
            raise ValidationError(
                "No 3CX API key configured! Generate one in "
                "Connect Settings → 3CX first.")
        odoo_url = (get_param("api_url") or get_param("web_base_url")
                    or "").rstrip("/")
        if not odoo_url:
            raise ValidationError(
                "Odoo API URL is not configured! Set connect.api_url "
                "(Connect Settings → General).")
        with file_open("connect_3cx/templates/crm_template.xml", "r") as f:
            template = f.read()
        return Template(template).substitute(
            odoo_url=odoo_url, api_key=api_key)

    def threecx_download_template(self):
        """Settings form button: download the generated CRM template."""
        self.ensure_one()
        if not self.sudo().get_param("threecx_api_key"):
            self.write({"display_threecx_api_key": secrets.token_urlsafe(24)})
        return {
            "type": "ir.actions.act_url",
            "url": "/3cx/template",
            "target": "self",
        }

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        """Click-to-call via the 3CX Web Client dial URL.

        There is no server-side originate API on the 3CX PRO tier, so the
        override returns an ir.actions.act_url opening the user's own 3CX
        Web Client with the number pre-filled — the call is placed there
        and lands in the ledger through the ReportCall journal webhook.
        """
        # Dispatch by the user's click-to-call provider; fall through to
        # other installed telephony modules when it is not 3CX.
        if self._get_originate_provider(user) != '3cx':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user, **kwargs)
        self.env["oduist.license"].check_license("connect", silent=False)
        if not isinstance(number, str) or not number.strip():
            raise ValidationError("No number to dial!")
        # Keep a leading + (URL-encoded below); drop formatting chars.
        number = re.sub(r"[\s().\-]", "", number)
        get_param = self.sudo().get_param
        pbx_url = get_param("threecx_pbx_url")
        if not get_param("threecx_enabled") or not pbx_url:
            raise ValidationError(
                "3CX integration is not configured! Enable it and set the "
                "PBX URL in Connect Settings → 3CX.")
        return {
            "type": "ir.actions.act_url",
            "url": "{}/webclient/#/call?phone={}".format(
                pbx_url.rstrip("/"), quote(number, safe="")),
            "target": "new",
        }
