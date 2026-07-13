# -*- coding: utf-8 -*-
import json
import logging
import uuid
from urllib.parse import urljoin, urlsplit

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import PROTECTED_FIELDS, debug, strip_number

ODUIST_MODULES.append('connect_asterisk')

# Mask the agent token the same way the core module masks openai_api_key.
if "display_asterisk_agent_token" not in PROTECTED_FIELDS:
    PROTECTED_FIELDS.append("display_asterisk_agent_token")

logger = logging.getLogger(__name__)

# Default AMI events the sidecar agent subscribes to / forwards.
DEFAULT_ASTERISK_EVENTS = (
    'Newchannel,Newstate,Hangup,NewConnectedLine,OriginateResponse,VarSet'
)


class Settings(models.Model):
    _inherit = "connect.settings"

    # Agent connection
    asterisk_enabled = fields.Boolean(
        string="Asterisk Enabled",
        default=False,
        help="Enable the Asterisk integration (agent sync, web phone).",
    )
    asterisk_agent_url = fields.Char(
        string="Agent URL",
        default="http://host.docker.internal:8082",
        help="Base URL of the Asterisk agent service. Odoo posts originate "
             "and AMI actions there. For Docker hosts, use "
             "host.docker.internal; otherwise the LAN IP of the host where "
             "the agent container runs next to Asterisk.",
    )
    asterisk_agent_token = fields.Char(
        string="Agent Token (stored)",
        groups="connect.group_admin",
    )
    display_asterisk_agent_token = fields.Char(
        string="Agent Token",
        help="Shared secret used by Odoo and the Asterisk agent to "
             "authenticate each other. Generate a fresh value (≥24 chars, "
             "[A-Za-z0-9_-]) and copy it into the ODOO_TOKEN env var of "
             "the agent before saving — the value is masked back to "
             "**** immediately afterwards. Visible only to administrators.",
    )

    # AMI connection (served to the agent via /asterisk/api/config)
    asterisk_ami_host = fields.Char(
        string="AMI Host",
        default="127.0.0.1",
        help="Asterisk host as reachable from the agent container.",
    )
    asterisk_ami_port = fields.Integer(string="AMI Port", default=5038)
    asterisk_ami_user = fields.Char(
        string="AMI User",
        default="connect-agent",
        help="manager.conf user. Required permissions: "
             "read = call,dialplan,user; write = originate,call,reporting.",
    )
    asterisk_ami_password = fields.Char(
        string="AMI Password",
        groups="connect.group_admin",
    )
    asterisk_events = fields.Char(
        string="AMI Events",
        default=DEFAULT_ASTERISK_EVENTS,
        help="Comma-separated AMI event names the agent forwards to Odoo. "
             "Keep the default unless you know what you are doing.",
    )

    # Originate
    asterisk_originate_context = fields.Char(
        string="Originate Context",
        default="from-internal",
        help="Default dialplan context for click-to-call originated calls. "
             "Can be overridden per endpoint.",
    )
    asterisk_originate_timeout = fields.Integer(
        string="Originate Timeout (sec)", default=60)

    # Recordings
    asterisk_recordings_enabled = fields.Boolean(
        string="Upload Recordings",
        default=True,
        help="When enabled, the agent uploads MixMonitor recordings to Odoo "
             "after hangup. Requires the agent to have the Asterisk monitor "
             "directory mounted.",
    )

    # Softphone
    asterisk_phone_enabled = fields.Boolean(
        string="Web Phone Enabled",
        help="Enable the JsSIP web phone for users with a WebRTC endpoint.",
    )
    asterisk_websocket_url = fields.Char(
        string="WebSocket URL",
        help="Asterisk SIP WebSocket URL the web phone registers to, "
             "e.g. wss://pbx.example.com:8089/ws.",
    )
    asterisk_sip_proxy = fields.Char(
        string="SIP Proxy",
        help="SIP domain/host used in the web phone SIP URI. Defaults to "
             "the WebSocket URL host when empty.",
    )
    asterisk_sip_realm = fields.Char(
        string="SIP Realm",
        default="asterisk",
        help="SIP authentication realm of the web phone registration.",
    )
    asterisk_stun_server = fields.Char(
        string="STUN Server",
        default="stun.l.google.com:19302",
    )
    asterisk_phone_trace_sip = fields.Boolean(string="Trace SIP")
    asterisk_attended_transfer_sequence = fields.Char(
        string="Attended Transfer Sequence", default="*7",
        help="DTMF feature code that starts an attended transfer "
             "(call forward) from the web phone.")
    asterisk_disconnect_call_sequence = fields.Char(
        string="Disconnect Call Sequence", default="**",
        help="DTMF feature code that cancels an attended transfer.")
    asterisk_transfer_contact_search = fields.Selection(
        [("extensions", "Extensions"), ("partners", "Partners"),
         ("all", "All")],
        string="Transfer Contact Search", default="all")

    # Status (filled by buttons / heartbeats)
    asterisk_agent_status = fields.Char(string="Agent Status", readonly=True)
    asterisk_agent_version = fields.Char(string="Agent Version", readonly=True)
    asterisk_last_heartbeat = fields.Datetime(
        string="Last Heartbeat", readonly=True)
    asterisk_core_status = fields.Char(string="Asterisk Status", readonly=True)

    @api.model
    def _validate_asterisk_agent_token(self, value):
        """Raise ValidationError on weak / malformed agent token."""
        if value in (False, None):
            return
        value = value.strip()
        if not value:
            return
        if len(value) < self._TOKEN_MIN_LEN:
            raise ValidationError(
                "Agent Token must be at least {} characters long.".format(
                    self._TOKEN_MIN_LEN
                )
            )
        bad = sorted({c for c in value if c not in self._TOKEN_ALLOWED_CHARS})
        if bad:
            raise ValidationError(
                "Agent Token can only contain letters, digits, '_' and '-'; "
                "remove: {}".format(" ".join(bad))
            )

    _TOKEN_MIN_LEN = 24
    _TOKEN_ALLOWED_CHARS = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    )

    def write(self, vals):
        # The core settings.write() does a second-pass write under the
        # 'skip_protected_fields' context to replace the displayed
        # secret with asterisks. Skip our validation in that pass so we
        # don't reject the masked value.
        if not self.env.context.get("skip_protected_fields"):
            if "display_asterisk_agent_token" in vals:
                self._validate_asterisk_agent_token(
                    vals["display_asterisk_agent_token"]
                )
        res = super().write(vals)
        # Nudge the agent to re-pull its config when Asterisk settings
        # change. Status fields are excluded — they are written by agent
        # heartbeats and the sync nudge would loop back to the agent.
        status_fields = {
            "asterisk_agent_status", "asterisk_agent_version",
            "asterisk_last_heartbeat", "asterisk_core_status",
        }
        if not self.env.context.get("skip_protected_fields"):
            if any((k.startswith("asterisk_") and k not in status_fields) or
                   k == "display_asterisk_agent_token" for k in vals):
                self.asterisk_agent_sync()
        return res

    @api.model
    def asterisk_agent_request(self, path, payload=None, method="POST",
                               timeout=6, raise_exc=True):
        """Send an authenticated HTTP request to the sidecar agent.

        Returns the parsed JSON response (or raw text when not JSON).
        Raises ValidationError on transport or HTTP errors unless
        raise_exc is False (then returns False).
        """
        agent_url = self.sudo().get_param("asterisk_agent_url")
        token = self.sudo().get_param("asterisk_agent_token")
        if not agent_url:
            if raise_exc:
                raise ValidationError(
                    "Asterisk Agent URL is not configured! "
                    "Set it in Connect Settings → Asterisk.")
            return False
        response = None
        try:
            response = requests.request(
                method,
                urljoin(agent_url, path),
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
            logger.warning("Asterisk agent request %s failed: %s", path, e)
            if raise_exc:
                if response is None:
                    raise ValidationError(
                        "Cannot reach the Asterisk agent: {}".format(e))
                raise ValidationError(response.text)
            return False

    @api.model
    def asterisk_ami_action(self, action, timeout=5, raise_exc=True):
        """Execute an AMI action on Asterisk through the agent.

        Args:
            action (dict): AMI action fields, e.g. {'Action': 'Ping'}.
        Returns the AMI response dict (or list of events) from the agent.
        """
        debug(self, "AMI action: {}".format(json.dumps(action)))
        return self.asterisk_agent_request(
            "/ami_action", {"action": action},
            timeout=timeout, raise_exc=raise_exc)

    @api.model
    def asterisk_agent_sync(self, scope="config"):
        """Schedule a sync notification to the agent after the commit.

        Multiple writes inside one transaction collapse into a single
        HTTP POST: postcommit callbacks dedupe by (function, args).
        Never raises; the agent re-pulls config periodically anyway.
        """
        settings = self.sudo()
        if not settings.get_param("asterisk_enabled"):
            return
        url = settings.get_param("asterisk_agent_url")
        token = settings.get_param("asterisk_agent_token")
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
                    "Asterisk agent sync notification to %s failed (%s); "
                    "the agent reconcile loop will catch up.",
                    sync_url, exc,
                )

        self.env.cr.postcommit.add(_send)

    def asterisk_ping_agent(self):
        """Settings form button: check agent liveness."""
        self.ensure_one()
        result = self.asterisk_agent_request("/api/status", method="GET")
        version = result.get("version") if isinstance(result, dict) else ""
        ami_ok = result.get("ami_connected") if isinstance(result, dict) else False
        self.write({
            "asterisk_agent_status": "UP — AMI {}".format(
                "connected" if ami_ok else "DISCONNECTED"),
            "asterisk_agent_version": version or "",
            "asterisk_last_heartbeat": fields.Datetime.now(),
        })
        self.env["connect.settings"].connect_notify(
            "Agent is up, AMI {}.".format(
                "connected" if ami_ok else "disconnected"),
            notify_uid=self.env.user.id)

    def check_asterisk_status(self):
        """Settings form button: fetch Asterisk core status via the agent."""
        self.ensure_one()
        result = self.asterisk_ami_action({"Action": "CoreStatus"})
        status = "UNKNOWN"
        if isinstance(result, dict):
            response = result.get("response")
            if isinstance(response, dict):
                startup = response.get("CoreStartupTime", "")
                calls = response.get("CoreCurrentCalls", "?")
                status = "UP — started {}, {} active call(s)".format(
                    startup, calls)
        self.write({"asterisk_core_status": status})

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        """Originate a call from the current user to the number (click-to-call).

        Pre-creates the first call leg with technical_direction
        'outbound-api' so that subsequent AMI events (sent with the same
        ChannelId) update it instead of creating a duplicate, then asks
        the agent to issue an AMI Originate per enabled endpoint.
        """
        # Dispatch by the user's click-to-call provider; fall through to
        # other installed telephony modules when it is not Asterisk.
        if self._get_originate_provider(user) != 'asterisk':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user, **kwargs)
        self.env["oduist.license"].check_license("connect", silent=False)
        number = strip_number(number)
        if not number:
            raise ValidationError("No number to dial!")
        user = user or self.env.user
        connect_user = self.env["connect.user"].sudo().search(
            [("user", "=", user.id)], limit=1)
        if not connect_user:
            raise ValidationError("PBX user is not defined!")
        endpoints = connect_user.asterisk_endpoint_ids.filtered(
            lambda e: e.asterisk_originate_enabled and e.asterisk_channel)
        if not endpoints:
            raise ValidationError(
                "No endpoints with originate enabled and an Asterisk "
                "channel defined!")
        # Resolve CallerID name from the reference record.
        callerid_name = ""
        if res_model and res_id and res_model != "connect.call":
            obj = self.env[res_model].browse(int(res_id))
            if obj.exists() and hasattr(obj, "name") and obj.name:
                callerid_name = "To: {}".format(obj.name)
        timeout = int(self.sudo().get_param("asterisk_originate_timeout") or 60)
        default_context = self.sudo().get_param("asterisk_originate_context")
        Channel = self.env["connect.channel"]
        Call = self.env["connect.call"]
        for endpoint in endpoints:
            channel_id = str(uuid.uuid4())
            other_channel_id = str(uuid.uuid4())
            channel = Channel.process_channel_event({
                "sid": channel_id,
                "caller": connect_user.asterisk_exten_number or endpoint.asterisk_sip_user,
                "called": number,
                "technical_direction": "outbound-api",
                "status": "queued",
                "caller_pbx_user_id": connect_user.id,
            })
            channel.asterisk_channel = endpoint.asterisk_channel
            Call.process_call_event(channel)
            variables = endpoint._get_originate_variables()
            action = {
                "Action": "Originate",
                "Context": endpoint.asterisk_originate_context or
                           default_context or "from-internal",
                "Priority": "1",
                "Timeout": 1000 * timeout,
                "Channel": endpoint.asterisk_channel,
                "Exten": number,
                "Async": "true",
                "EarlyMedia": "true",
                "CallerID": "{} <{}>".format(callerid_name, number),
                "ChannelId": channel_id,
                "OtherChannelId": other_channel_id,
                "Variable": variables,
            }
            result = self.asterisk_ami_action(action, raise_exc=False)
            if result is False or (
                    isinstance(result, dict)
                    and isinstance(result.get("response"), dict)
                    and result["response"].get("Response") == "Error"):
                message = "Agent unreachable"
                if isinstance(result, dict):
                    message = result.get("response", {}).get(
                        "Message", message)
                channel = Channel.sudo().process_channel_event({
                    "sid": channel_id,
                    "caller": connect_user.asterisk_exten_number or
                              endpoint.asterisk_sip_user,
                    "called": number,
                    "technical_direction": "outbound-api",
                    "status": "failed",
                })
                Call.process_call_event(channel, error_data={
                    "error_code": "originate-error",
                    "error_message": message,
                })
                self.connect_notify(
                    "Call to {} failed: {}".format(number, message),
                    notify_uid=user.id, warning=True)
        return True

    @api.model
    def asterisk_get_agent_config(self):
        """Config payload served to the agent on /asterisk/api/config."""
        get_param = self.sudo().get_param
        events = get_param("asterisk_events") or DEFAULT_ASTERISK_EVENTS
        return {
            "ami": {
                "host": get_param("asterisk_ami_host"),
                "port": int(get_param("asterisk_ami_port") or 5038),
                "user": get_param("asterisk_ami_user"),
                "password": get_param("asterisk_ami_password"),
            },
            "events": [e.strip() for e in events.split(",") if e.strip()],
            "recordings_enabled": bool(
                get_param("asterisk_recordings_enabled")),
        }

    @api.model
    def asterisk_get_phone_settings(self):
        """Web phone configuration for the JsSIP client.

        The payload keys mirror what the phone component consumes in
        ``initUserAgent`` — every ``user_agent`` value must be non-empty
        for the phone to activate.
        """
        get_param = self.sudo().get_param
        websocket = get_param("asterisk_websocket_url") or ""
        proxy = get_param("asterisk_sip_proxy")
        if not proxy and websocket:
            proxy = urlsplit(websocket).hostname or ""
        return {
            "phone_enabled": bool(get_param("asterisk_enabled"))
                             and bool(get_param("asterisk_phone_enabled")),
            "user_agent": {
                "phone_sip_protocol": "wss",
                "phone_sip_proxy": proxy,
                "phone_websocket": websocket,
                "phone_stun_server": get_param("asterisk_stun_server"),
                "phone_realm": get_param("asterisk_sip_realm"),
            },
            "attended_transfer_sequence": get_param(
                "asterisk_attended_transfer_sequence") or "*7",
            "disconnect_call_sequence": get_param(
                "asterisk_disconnect_call_sequence") or "**",
            "transfer_contact_search": get_param(
                "asterisk_transfer_contact_search") or "all",
            "trace_sip": bool(get_param("asterisk_phone_trace_sip")),
            "phone_sip_auth_user_enabled": False,
        }
