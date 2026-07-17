# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class Number(models.Model):
    _name = 'connect.infobip.number'
    _description = 'Infobip Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    number_key = fields.Char(readonly=True)
    capabilities = fields.Char(readonly=True)
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('external', 'External Number'),
    ], ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    external_number = fields.Char(
        help='E.164 number inbound voice calls are forwarded to.')
    external_callerid_mode = fields.Selection(
        selection=[('did', 'This Number'), ('caller', 'Original Caller')],
        default='did', string='External CallerID',
        help="Caller ID presented on the forwarded leg. 'Original Caller' "
             "passes the calling party's number through and requires CLI "
             "passthrough entitlement on the Infobip account.")
    is_ignored = fields.Boolean('Ignored')

    def update_infobip_number(self):
        """Push per-number config to Infobip: SMS forward-to-HTTP to our
        inbound webhook and the voice forward-to-application action.

        Both pushes are best-effort: the Numbers API configuration schema
        varies and must be confirmed live (ADR-036); a failure degrades to
        a warning with manual portal instructions. Voice ROUTING (user vs
        external number) lives in Odoo and needs no Infobip-side change.
        """
        self.ensure_one()
        if self.is_ignored:
            debug(self, 'Ignoring number {} update.'.format(self.phone_number))
            return
        Settings = self.env['connect.settings']
        capabilities = self.capabilities or ''
        if 'SMS' in capabilities:
            try:
                self._infobip_push_sms_forwarding()
            except Exception as e:
                logger.warning(
                    'SMS forwarding config for %s failed: %s',
                    self.phone_number, e)
                Settings.connect_notify(
                    'Could not configure SMS forwarding for {} ({}). In the '
                    'Infobip portal set the number\'s SMS action to "Forward '
                    'to HTTP" with the Inbound SMS URL from Infobip '
                    'Settings.'.format(self.phone_number, e),
                    title='Infobip Sync', warning=True)
        if 'VOICE' in capabilities:
            try:
                self._infobip_push_voice_action()
            except Exception as e:
                logger.warning(
                    'Voice action config for %s failed: %s',
                    self.phone_number, e)
                Settings.connect_notify(
                    'Could not configure voice forwarding for {} ({}). In '
                    'the Infobip portal point the number\'s voice action to '
                    'the "Odoo Connect" Calls configuration.'.format(
                        self.phone_number, e),
                    title='Infobip Sync', warning=True)

    def _infobip_push_sms_forwarding(self):
        """Set the number's catch-all SMS action to POST to our webhook."""
        self.ensure_one()
        Settings = self.env['connect.settings']
        url = Settings.get_infobip_webhook_url('message')
        base = '/numbers/1/numbers/{}/sms'.format(self.number_key)
        existing = Settings.infobip_api_request('GET', base)
        configs = (existing.get('configurations') or existing.get('results')
                   or [])
        payload = {
            'action': {
                'type': 'HTTP_FORWARD',
                'url': url,
                'httpMethod': 'POST',
                'contentType': 'application/json',
            },
        }
        current = None
        for config in configs:
            if not config.get('keyword'):
                current = config
                break
        if current and current.get('key'):
            Settings.infobip_api_request(
                'PUT', '{}/{}'.format(base, current['key']), payload)
        else:
            Settings.infobip_api_request('POST', base, payload)
        debug(self, 'SMS forwarding for {} set to the Odoo webhook.'.format(
            self.phone_number))

    def _infobip_push_voice_action(self):
        """Point the number's voice action at our Calls configuration."""
        self.ensure_one()
        Settings = self.env['connect.settings']
        cfg = Settings.sudo().get_param('infobip_calls_configuration_id')
        if not cfg:
            debug(self, 'No Calls configuration yet, voice action for {} '
                        'left unset.'.format(self.phone_number),
                  level='warning')
            return
        base = '/numbers/1/numbers/{}/voice'.format(self.number_key)
        payload = {
            'action': {
                'type': 'FORWARD_TO_SUBSCRIPTION',
                'callsConfigurationId': cfg,
            },
        }
        Settings.infobip_api_request('POST', base, payload)
        debug(self, 'Voice action for {} set to the Calls configuration.'.format(
            self.phone_number))

    def write(self, vals):
        if 'destination' in vals:
            keep = {'user': 'user', 'external': 'external_number'}.get(
                vals['destination'])
            for field in ['user', 'external_number']:
                if field != keep:
                    vals.update({field: None})
        res = super().write(vals)
        if not self.env['connect.settings'].get_param('infobip_auto_sync'):
            return res
        for rec in self:
            if not self.env.context.get('skip_infobip_sync'):
                rec.update_infobip_number()
        return res

    @api.model
    def sync(self):
        Settings = self.env['connect.settings']
        numbers = Settings.infobip_list_numbers()
        seen_keys = []
        for number in numbers:
            number_key = number.get('numberKey') or number.get('key') or ''
            phone = number.get('number') or number.get('phoneNumber') or ''
            if phone and not phone.startswith('+'):
                phone = '+{}'.format(phone)
            capabilities = number.get('capabilities') or []
            if isinstance(capabilities, dict):
                capabilities = [k for k, v in capabilities.items() if v]
            vals = {
                'phone_number': phone,
                'number_key': number_key,
                'capabilities': ','.join(
                    str(c).upper() for c in capabilities),
            }
            seen_keys.append(number_key)
            rec = self.search([('number_key', '=', number_key)])
            if not rec:
                rec = self.search([('phone_number', '=', phone)])
            if not rec:
                vals['friendly_name'] = number.get('friendlyName') or ''
                rec = self.with_context(skip_infobip_sync=True).create(vals)
                rec.update_infobip_number()
                Settings.connect_notify(
                    title='Infobip Sync',
                    message='Number {} added'.format(phone),
                )
            else:
                rec.with_context(skip_infobip_sync=True).write(vals)
                rec.update_infobip_number()
        # Remove numbers that exist only in Odoo
        numbers_to_remove = self.search(
            [
                ('number_key', 'not in', seen_keys),
                ('number_key', '!=', False),
            ]
        )
        if numbers_to_remove:
            user_message = 'Number(s) {} removed in Infobip!'.format(
                ','.join(
                    [k.phone_number for k in numbers_to_remove]
                )
            )
            numbers_to_remove.unlink()
            Settings.connect_notify(
                title='Infobip Sync',
                warning=True,
                sticky=True,
                message=user_message,
            )

    @api.model
    def route_call(self, event):
        """Route an inbound PSTN call (CALL_RECEIVED) by the called DID."""
        channel = self.env['connect.channel'].on_infobip_event(event)
        if not channel:
            return
        self.env['connect.call'].process_call_event(channel)
        if not self.env['oduist.license'].check_license('connect', silent=True):
            channel.infobip_answer_say_hangup('Service unavailable.')
            return
        called = channel.to or channel.called or ''
        stripped = called.lstrip('+')
        number = self.sudo().search([
            ('phone_number', 'in', [called, stripped, '+' + stripped]),
        ], limit=1)
        if not number or number.is_ignored or not number.destination:
            debug(self, 'Inbound number {} not configured.'.format(called),
                  level='warning')
            channel.infobip_answer_say_hangup(
                'This number is not configured. Goodbye!')
            return
        channel.infobip_route_number = number
        if number.destination == 'external' and number.external_number:
            channel._infobip_bridge_external(number)
        elif number.destination == 'user' and number.user:
            channel._infobip_start_user_ring(number.user)
        else:
            channel.infobip_answer_say_hangup(
                'This number is not configured. Goodbye!')
