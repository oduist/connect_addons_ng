# -*- coding: utf-8 -*-
import logging
import re
import secrets
from string import Template
from urllib.parse import quote

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import file_open

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import PROTECTED_FIELDS

ODUIST_MODULES.append('connect_3cx')

# Mask the webhook API key the same way the core module masks openai_api_key.
if "display_threecx_api_key" not in PROTECTED_FIELDS:
    PROTECTED_FIELDS.append("display_threecx_api_key")
if "display_threecx_client_secret" not in PROTECTED_FIELDS:
    PROTECTED_FIELDS.append("display_threecx_client_secret")

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

    # --- Deep tier: Call Control sidecar agent (ADR-035) --------------
    threecx_agent_enabled = fields.Boolean(
        string="Agent Enabled",
        default=False,
        help="Enable the deep integration through the oduist/3cx-agent "
             "sidecar: live call events over the Call Control WebSocket, "
             "server-side click-to-call and recording download. Requires "
             "the 3CX AI edition (8SC+) and a dedicated 3CX API client "
             "application.",
    )
    threecx_agent_url = fields.Char(
        string="Agent URL",
        default="http://host.docker.internal:8083",
        help="Base URL of the 3CX agent service. Odoo posts originate "
             "and sync requests there. For Docker hosts, use "
             "host.docker.internal; otherwise the LAN IP of the host "
             "where the agent container runs.",
    )
    threecx_client_id = fields.Char(
        string="3CX Client ID",
        help="Client ID (DN) of the dedicated 3CX API client application "
             "(Admin Console → Integrations → API) with both the Call "
             "Control and the Configuration API scopes. The agent must "
             "be its only consumer — 3CX keeps a single active token "
             "per client application.",
    )
    threecx_client_secret = fields.Char(
        string="3CX Client Secret (stored)",
        groups="connect.group_admin",
    )
    display_threecx_client_secret = fields.Char(
        string="3CX Client Secret",
        help="API key of the 3CX client application; shown once by the "
             "3CX Admin Console at creation. Masked back to **** after "
             "saving. Visible only to administrators.",
    )
    threecx_recordings_enabled = fields.Boolean(
        string="Download Recordings",
        default=True,
        help="When enabled, the agent polls the 3CX Configuration API "
             "for finished call recordings and uploads the audio to "
             "Odoo (requires the System Owner role on the API client).",
    )
    threecx_originate_timeout = fields.Integer(
        string="Originate Timeout (sec)", default=30)
    # Status (filled by buttons / heartbeats)
    threecx_agent_status = fields.Char(string="Agent Status", readonly=True)
    threecx_agent_version = fields.Char(
        string="Agent Version", readonly=True)
    threecx_last_heartbeat = fields.Datetime(
        string="Last Heartbeat", readonly=True)

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
        res = super().write(vals)
        # Nudge the agent to re-pull its config when 3CX settings
        # change. Status fields are excluded — they are written by
        # webhooks/heartbeats and the sync nudge would loop back.
        status_fields = {
            "threecx_agent_status", "threecx_agent_version",
            "threecx_last_heartbeat", "threecx_last_lookup",
            "threecx_last_journal",
        }
        if not self.env.context.get("skip_protected_fields"):
            if any((k.startswith("threecx_") and k not in status_fields)
                   or k.startswith("display_threecx") for k in vals):
                self.threecx_agent_sync()
        return res

    @api.model
    def threecx_agent_request(self, path, payload=None, method="POST",
                              timeout=10, raise_exc=True):
        """Send an authenticated HTTP request to the sidecar agent.

        Returns the parsed JSON response (or raw text when not JSON).
        Raises ValidationError on transport or HTTP errors unless
        raise_exc is False (then returns False).
        """
        agent_url = self.sudo().get_param("threecx_agent_url")
        token = self.sudo().get_param("threecx_api_key")
        if not agent_url:
            if raise_exc:
                raise ValidationError(
                    "3CX Agent URL is not configured! "
                    "Set it in Connect Settings → 3CX.")
            return False
        response = None
        try:
            response = requests.request(
                method,
                agent_url.rstrip("/") + path,
                headers={"Authorization": "Bearer {}".format(token or "")},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            try:
                return response.json()
            except ValueError:
                return response.text
        except Exception as e:
            logger.warning("3CX agent request %s failed: %s", path, e)
            if raise_exc:
                if response is None:
                    raise ValidationError(
                        "Cannot reach the 3CX agent: {}".format(e))
                raise ValidationError(response.text)
            return False

    @api.model
    def threecx_agent_sync(self, scope="config"):
        """Schedule a sync notification to the agent after the commit.

        Multiple writes inside one transaction collapse into a single
        HTTP POST: postcommit callbacks dedupe by (function, args).
        Never raises; the agent re-pulls config periodically anyway.
        """
        settings = self.sudo()
        if not settings.get_param("threecx_agent_enabled"):
            return
        url = settings.get_param("threecx_agent_url")
        token = settings.get_param("threecx_api_key")
        if not url or not token:
            return
        sync_url = url.rstrip("/") + "/sync"

        def _send():
            try:
                requests.post(
                    sync_url,
                    json={"scope": scope},
                    headers={"Authorization": "Bearer " + token},
                    timeout=3,
                )
            except Exception as exc:
                logger.warning(
                    "3CX agent sync notification to %s failed (%s); "
                    "the agent reconcile loop will catch up.",
                    sync_url, exc,
                )

        self.env.cr.postcommit.add(_send)

    def threecx_ping_agent(self):
        """Settings form button: check agent liveness."""
        self.ensure_one()
        result = self.threecx_agent_request("/api/status", method="GET")
        version = result.get("version") if isinstance(result, dict) else ""
        ws_ok = result.get("ws_connected") \
            if isinstance(result, dict) else False
        self.write({
            "threecx_agent_status": "UP — Call Control WS {}".format(
                "connected" if ws_ok else "DISCONNECTED"),
            "threecx_agent_version": version or "",
            "threecx_last_heartbeat": fields.Datetime.now(),
        })
        self.env["connect.settings"].connect_notify(
            "Agent is up, Call Control WebSocket {}.".format(
                "connected" if ws_ok else "disconnected"),
            notify_uid=self.env.user.id)

    @api.model
    def threecx_get_agent_config(self):
        """Config payload served to the agent on /3cx/api/config."""
        get_param = self.sudo().get_param
        return {
            "pbx_url": (get_param("threecx_pbx_url") or "").rstrip("/"),
            "client_id": get_param("threecx_client_id") or "",
            "client_secret": get_param("threecx_client_secret") or "",
            "recordings_enabled": bool(
                get_param("threecx_recordings_enabled")),
        }

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
        """Click-to-call dispatcher for the 3CX provider.

        Deep tier (agent enabled): server-side originate through the
        sidecar agent (Call Control makecall) — the call rings the
        user's own 3CX devices; a leg is pre-created when the PBX
        returns call/leg ids so WS events update instead of duplicate.

        Fallback (agent disabled or unreachable): an ir.actions.act_url
        opening the 3CX Web Client with the number pre-filled — the
        call is placed there and lands in the ledger through the
        ReportCall journal webhook (phase 1, ADR-034).
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
        if not get_param("threecx_enabled"):
            raise ValidationError(
                "3CX integration is not configured! Enable it in "
                "Connect Settings → 3CX.")
        if get_param("threecx_agent_enabled"):
            result = self._threecx_originate_via_agent(number, user)
            if result is not None:
                return result
            # Agent unreachable: fall back to the dial URL below.
        pbx_url = get_param("threecx_pbx_url")
        if not pbx_url:
            raise ValidationError(
                "3CX PBX URL is not configured! Set it in "
                "Connect Settings → 3CX.")
        return {
            "type": "ir.actions.act_url",
            "url": "{}/webclient/#/call?phone={}".format(
                pbx_url.rstrip("/"), quote(number, safe="")),
            "target": "new",
        }

    @api.model
    def _threecx_originate_via_agent(self, number, user=None):
        """Server-side originate through the agent.

        Returns True on success, None when the agent cannot be reached
        (the caller falls back to the dial URL). Raises on user
        misconfiguration (no extension) — falling back would not help.
        """
        user = user or self.env.user
        connect_user = self.env["connect.user"].sudo().search(
            [("user", "=", user.id)], limit=1)
        if not connect_user or not connect_user.threecx_exten:
            raise ValidationError(
                "3CX extension is not set on the Connect user!")
        timeout = int(
            self.sudo().get_param("threecx_originate_timeout") or 30)
        result = self.threecx_agent_request("/originate", {
            "dn": connect_user.threecx_exten,
            "destination": number,
            "timeout": timeout,
        }, raise_exc=False)
        if result is False or not isinstance(result, dict):
            logger.warning(
                "3CX agent originate unavailable; falling back to the "
                "Web Client dial URL.")
            return None
        # Pre-create the leg when the PBX returned call/leg ids so the
        # subsequent WS events update it instead of duplicating
        # (ADR-026 originate pattern). The makecall result shape is
        # only partially documented — probe both casings.
        response = result.get("response")
        res_obj = {}
        if isinstance(response, dict):
            res_obj = response.get("result") or response.get("Result") or {}
        if not isinstance(res_obj, dict):
            res_obj = {}
        callid = res_obj.get("callid") or res_obj.get("CallId")
        legid = res_obj.get("legid") or res_obj.get("LegId")
        if callid and legid:
            Channel = self.env["connect.channel"]
            channel = Channel.process_channel_event({
                "sid": "3cxcc-{}-{}".format(callid, legid),
                "caller": connect_user.threecx_exten,
                "called": number,
                "technical_direction": "outbound-api",
                "status": "queued",
                "caller_pbx_user_id": connect_user.id,
            })
            channel.write({
                "threecx_callid": str(callid),
                "threecx_legid": str(legid),
            })
            self.env["connect.call"].process_call_event(channel)
        self.connect_notify(
            "Calling {}...".format(number), notify_uid=user.id)
        return True
