# -*- coding: utf-8 -*-
import asyncio
import datetime
import logging
import secrets
from urllib.parse import urlsplit, urlunsplit

from odoo import api, fields, models, release
from odoo.exceptions import ValidationError

from livekit import api as lk_api

from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_livekit')

logger = logging.getLogger(__name__)

LIVEKIT_PROTECTED_FIELDS = [
    "display_livekit_api_secret",
    "display_deepgram_api_key",
    "display_elevenlabs_api_key",
]


class Settings(models.Model):
    _inherit = "connect.settings"

    # LiveKit server connection. The WS URL is what browsers and the agent
    # worker connect to; the HTTP API URL is derived from it unless set
    # explicitly (e.g. when the server sits behind a different ingress).
    livekit_ws_url = fields.Char(string="LiveKit WS URL")
    livekit_api_url = fields.Char(
        string="LiveKit API URL",
        help="Optional HTTP(S) URL of the LiveKit server API. When empty it "
             "is derived from the WS URL (ws → http, wss → https).")
    # Never grant these to connect.group_webhook: the webhook user is the
    # identity of all public webhook controllers, and get_param() returns
    # groups-restricted fields to group members (ADR-025).
    livekit_api_key = fields.Char(
        string="LiveKit API Key", groups="base.group_erp_manager")
    livekit_api_secret = fields.Char(groups="base.group_erp_manager")
    display_livekit_api_secret = fields.Char(string="LiveKit API Secret")
    # Address of the livekit-sip service, shown to the admin for configuring
    # the SIP trunk on the carrier side. Odoo itself does not dial it.
    livekit_sip_uri = fields.Char(string="LiveKit SIP URI")
    livekit_verify_webhooks = fields.Boolean(
        default=True, string="Verify LiveKit Webhooks")
    livekit_auto_sync = fields.Boolean(default=True)
    # Shared secret for the agent worker / recording uploader sidecar
    # (Bearer auth on /livekit/api/* and /livekit/webhook/recording/*).
    livekit_agent_token = fields.Char(groups="base.group_erp_manager")
    # AI provider keys for the voice-agent worker. Named without the
    # livekit_ prefix on purpose: like openai_api_key in core these are
    # vendor keys, not LiveKit resources (ADR-037).
    deepgram_api_key = fields.Char(groups="base.group_erp_manager")
    display_deepgram_api_key = fields.Char(string="Deepgram API Key")
    elevenlabs_api_key = fields.Char(groups="base.group_erp_manager")
    display_elevenlabs_api_key = fields.Char(string="ElevenLabs API Key")

    @api.model
    def _livekit_api_url(self):
        api_url = self.sudo().get_param("livekit_api_url")
        if api_url:
            return api_url
        ws_url = self.sudo().get_param("livekit_ws_url")
        if not ws_url:
            raise ValidationError("Set the LiveKit WS URL first!")
        parts = urlsplit(ws_url)
        scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
        return urlunsplit((scheme, parts.netloc, parts.path, "", ""))

    @api.model
    def _livekit_credentials(self):
        # connect.settings is admin-only; credentials are read with sudo()
        # so no caller-level model access check is needed here.
        api_key = self.sudo().get_param("livekit_api_key")
        api_secret = self.sudo().get_param("livekit_api_secret")
        if not api_key or not api_secret:
            raise ValidationError("Set the LiveKit API key and secret first!")
        return api_key, api_secret

    @api.model
    def livekit_api_call(self, path, request=None):
        """Run one LiveKit server API call from synchronous Odoo code.

        ``path`` is ``"<service>.<method>"`` on ``livekit.api.LiveKitAPI``
        (e.g. ``"room.create_room"``, ``"sip.create_sip_participant"``).
        The SDK is asyncio-only, so every call runs a private event loop:
        only use this from threaded HTTP/cron workers, never from the
        gevent websocket worker where a loop may already be running.
        """
        api_key, api_secret = self._livekit_credentials()
        url = self._livekit_api_url()
        service_name, method_name = path.split(".")

        async def _run():
            client = lk_api.LiveKitAPI(url, api_key, api_secret)
            try:
                method = getattr(getattr(client, service_name), method_name)
                if request is None:
                    return await method()
                return await method(request)
            finally:
                await client.aclose()

        try:
            return asyncio.run(_run())
        except RuntimeError as exc:
            raise ValidationError(
                "LiveKit API calls must run in a threaded worker "
                "(no active event loop): {}".format(exc)) from exc
        except lk_api.TwirpError as exc:
            raise ValidationError(
                "LiveKit API error ({}): {}".format(exc.code, exc.message)
            ) from exc

    @api.model
    def livekit_create_token(self, identity, name=None, room_name=None,
                             ttl=3600, room_admin=False, metadata=None):
        """Mint a LiveKit room access JWT. Pure-sync, no server round-trip."""
        api_key, api_secret = self._livekit_credentials()
        token = lk_api.AccessToken(api_key, api_secret).with_identity(identity)
        if name:
            token = token.with_name(name)
        if metadata:
            token = token.with_metadata(metadata)
        grants = lk_api.VideoGrants(room_join=True)
        if room_name:
            grants.room = room_name
        if room_admin:
            grants.room_admin = True
        return (
            token.with_grants(grants)
            .with_ttl(datetime.timedelta(seconds=ttl))
            .to_jwt()
        )

    def livekit_sync(self):
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            # Connectivity + credentials check.
            self.livekit_api_call("room.list_rooms", lk_api.ListRoomsRequest())
            # Provider config models push their LiveKit resources themselves;
            # the guard keeps early commits of the module functional.
            for model_name in ("connect.livekit.trunk",
                               "connect.livekit.number",
                               "connect.livekit.outgoing_callerid"):
                if model_name in self.env:
                    self.env[model_name].sync()
            self.connect_notify(
                "LiveKit server synced successfully", title="Sync Complete")
        except ValidationError as e:
            if 'unauthorized' in str(e).lower() or '401' in str(e):
                raise ValidationError(
                    'Error authenticating requests to the LiveKit API! '
                    'Check your API key and secret!')
            raise

    def action_generate_livekit_agent_token(self):
        self.sudo().set_param(
            "livekit_agent_token", secrets.token_urlsafe(32))
        self.connect_notify(
            "LiveKit agent token regenerated. Update the worker environment!",
            title="LiveKit")

    def write(self, vals):
        if self.env.context.get("skip_protected_fields"):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in LIVEKIT_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace("display_", ""): vals.get(
                            field_name
                        ),
                        field_name: "*" * len(vals.get(field_name)),
                    }
                )
        if changed_fields:
            self.with_context(
                skip_protected_fields=True
            ).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
        return res
