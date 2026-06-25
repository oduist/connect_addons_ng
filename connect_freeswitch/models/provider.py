"""FreeSWITCH provider adapter — implements abstracts on
`connect.provider` (ODU-4 originate, ODU-15 webhook auth)."""
import logging
import secrets

from odoo import models

logger = logging.getLogger(__name__)


class FreeSwitchProvider(models.Model):
    _inherit = 'connect.provider'

    def _originate_call(self, number, res_model=None, res_id=None, **kwargs):
        if self.code != 'freeswitch':
            return super()._originate_call(
                number=number, res_model=res_model, res_id=res_id, **kwargs
            )
        # `user` and other Twilio-only kwargs are accepted-and-ignored
        # because the unified façade may pass them through.
        return self.env['connect.call']._freeswitch_originate_call(
            number=number, res_model=res_model, res_id=res_id,
        )

    def _phone_adapter_module(self):
        if self.code != 'freeswitch':
            return super()._phone_adapter_module()
        return 'connect_freeswitch/static/src/js/phone_service.js'

    def _get_webrtc_config(self, user=None):
        if self.code != 'freeswitch':
            return super()._get_webrtc_config(user=user)
        return self.env['connect.settings'].sudo().get_webrtc_config()

    def _verify_webhook(self, request, data=None):
        """Bearer-token auth (ADR-015 / ODU-15). Used by the firewall
        service ↔ Odoo direction; the same token authenticates Odoo
        when it POSTs `/firewall/sync` to the service."""
        if self.code != 'freeswitch':
            return super()._verify_webhook(request, data=data)
        expected = self.env['connect.settings'].sudo()._get().firewall_service_token or ''
        if not expected:
            return False
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.lower().startswith('bearer '):
            return False
        ok = secrets.compare_digest(auth[7:].strip(), expected)
        if not ok:
            logger.warning('FreeSWITCH firewall webhook token mismatch')
        return ok
