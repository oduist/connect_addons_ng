import logging
import re
from odoo import models, api
from odoo.exceptions import UserError
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

# FreeSWITCH hangup causes → connect call statuses
HANGUP_CAUSE_MAP = {
    'NORMAL_CLEARING': 'completed',
    'ORIGINATOR_CANCEL': 'canceled',
    'USER_BUSY': 'busy',
    'NO_ANSWER': 'no-answer',
    'NO_USER_RESPONSE': 'no-answer',
    'CALL_REJECTED': 'busy',
    'NORMAL_TEMPORARY_FAILURE': 'failed',
    'RECOVERY_ON_TIMER_EXPIRY': 'no-answer',
    'UNALLOCATED_NUMBER': 'failed',
    'SUBSCRIBER_ABSENT': 'failed',
    'DESTINATION_OUT_OF_ORDER': 'failed',
    'INVALID_NUMBER_FORMAT': 'failed',
    'NORMAL_UNSPECIFIED': 'completed',
}


class Call(models.Model):
    _inherit = 'connect.call'

    @api.model
    def originate_call(self, number, res_model=None, res_id=None):
        """Originate a call via FreeSWITCH.

        Rings the current user's endpoints (a-leg), then bridges to the
        target number via the matching outgoing route (b-leg).
        For internal extensions, bridges directly without a gateway.
        """
        self.env['oduist.license'].check_license('connect', silent=False)
        settings = self.env['connect.settings']

        number = re.sub(r'[\s()\-]', '', number or '')
        if not number:
            raise UserError("No phone number provided.")

        domain = settings.get_param('freeswitch_domain')
        if not domain:
            raise UserError("FreeSWITCH domain is not configured.")

        # Resolve partner
        partner_id = False
        caller_name = ''
        if res_model and res_id:
            obj = self.env[res_model].browse(res_id)
            if obj.exists():
                if res_model == 'res.partner':
                    partner_id = res_id
                    caller_name = obj.display_name
                elif hasattr(obj, 'partner_id') and obj.partner_id:
                    partner_id = obj.partner_id.id
                    caller_name = obj.partner_id.display_name
                elif hasattr(obj, 'partner') and obj.partner:
                    partner_id = obj.partner.id
                    caller_name = obj.partner.display_name

        # Get current user's connect_user and endpoints
        user = self.env.user
        connect_user = self.env['connect.user'].search([
            ('user', '=', user.id),
            ('active', '=', True),
        ], limit=1)
        if not connect_user:
            raise UserError("You don't have a Connect user configured.")

        endpoints = self.env['connect.endpoint'].search([
            ('connect_user_id', '=', connect_user.id),
            ('active', '=', True),
        ])
        # Filter to ringable endpoints (SIP with ring, or WebRTC with ring)
        ring_endpoints = endpoints.filtered(
            lambda ep: (ep.sip_enabled and ep.sip_ring)
            or (ep.webrtc_enabled and ep.webrtc_ring)
        )
        if not ring_endpoints:
            raise UserError("You don't have any ringable endpoints configured.")

        # Build a-leg (user's endpoints)
        a_leg_parts = []
        for ep in ring_endpoints:
            a_leg_parts.append(
                '[leg_timeout=30]user/{}@{}'.format(
                    ep.auth_user, domain))
        a_leg = ','.join(a_leg_parts)

        # Caller ID
        caller_number = connect_user.exten_number or ring_endpoints[0].auth_user

        # Check if target is an internal extension
        exten = self.env['connect.exten'].search(
            [('number', '=', number)], limit=1)
        if exten:
            # Internal call — bridge to extension's endpoints
            target_user = self.env['connect.user'].search([
                ('exten', '=', exten.id),
                ('active', '=', True),
            ], limit=1)
            if target_user:
                target_endpoints = self.env['connect.endpoint'].search([
                    ('connect_user_id', '=', target_user.id),
                    ('active', '=', True),
                ]).filtered(
                    lambda ep: (ep.sip_enabled and ep.sip_ring)
                    or (ep.webrtc_enabled and ep.webrtc_ring)
                )
                if target_endpoints:
                    b_parts = []
                    for ep in target_endpoints:
                        b_parts.append(
                            'user/{}@{}'.format(ep.auth_user, domain))
                    b_leg = ','.join(b_parts)
                else:
                    b_leg = 'user/{}@{}'.format(number, domain)
            else:
                b_leg = 'user/{}@{}'.format(number, domain)
        else:
            # External call — find outgoing route
            routes = self.env['connect.freeswitch.outgoing_route'].sudo().search(
                [('active', '=', True)])
            b_leg = None
            for route in routes:
                if re.match(route.pattern, number):
                    b_leg = self.env[
                        'connect.freeswitch.outgoing_route'
                    ]._build_bridge_data(
                        route.gateway.name, number,
                        strip=route.strip, prefix=route.prefix or '')
                    break
            if not b_leg:
                raise UserError(
                    "No outgoing route found for number: {}".format(number))

        # Build originate command
        variables = [
            "origination_caller_id_name='{}'".format(
                (caller_name or caller_number).replace("'", "")),
            "origination_caller_id_number={}".format(caller_number),
            "odoo_caller_pbx_user_id={}".format(connect_user.id),
        ]
        if partner_id:
            variables.append("odoo_partner_id={}".format(partner_id))

        # For external calls via gateway, force standard codecs on b-leg
        # since a-leg may be WebRTC (Opus) which gateways don't support
        if not exten:
            b_leg = '[absolute_codec_string=PCMU,PCMA]{}'.format(b_leg)

        cmd = '{{{}}}{} &bridge({})'.format(
            ','.join(variables), a_leg, b_leg)

        debug(self, 'FreeSWITCH originate: %s' % cmd)
        result = settings.freeswitch_api('originate', cmd)
        if not result or result.startswith('-ERR'):
            logger.error("FreeSWITCH originate failed: %s", result)
            raise UserError(
                "Failed to originate call: {}".format(result or 'no response'))

        return True

    @api.model
    def on_freeswitch_cdr(self, cdr_data):
        """Process a FreeSWITCH CDR event.

        Args:
            cdr_data: dict parsed from mod_xml_cdr XML with keys:
                uuid (str): FreeSWITCH channel UUID
                caller (str): Caller ID number
                called (str): Destination number
                direction (str): 'inbound' or 'outbound'
                hangup_cause (str): FreeSWITCH hangup cause
                duration (int): Call duration in seconds (billsec)
                caller_pbx_user_id (int): connect.user ID from channel variable (optional)
                called_pbx_user_id (int): connect.user ID (optional)
                other_leg_uuid (str): Other leg UUID for linking (optional)

        Returns:
            call id or False
        """
        self = self.sudo()
        debug(self, 'FreeSWITCH CDR: %s' % cdr_data)

        status = HANGUP_CAUSE_MAP.get(
            cdr_data.get('hangup_cause', ''), 'failed')

        # Map FreeSWITCH direction to Twilio-compatible technical_direction
        fs_direction = cdr_data.get('direction', '')
        if fs_direction == 'outbound':
            technical_direction = 'outbound-api'
        else:
            technical_direction = 'inbound'

        generic_params = {
            'sid': cdr_data['uuid'],
            'caller': cdr_data.get('caller', ''),
            'called': cdr_data.get('called', ''),
            'technical_direction': technical_direction,
            'status': status,
            'duration': int(cdr_data.get('duration', 0)),
            'call_type': 'phone',
            'parent_sid': cdr_data.get('other_leg_uuid'),
        }

        # Override called with DID number for inbound calls
        odoo_number_id = cdr_data.get('odoo_number_id')
        if odoo_number_id:
            number = self.env['connect.number'].browse(odoo_number_id).exists()
            if number:
                generic_params['called'] = number.phone_number

        # Pass direct user IDs from FreeSWITCH channel variables
        if cdr_data.get('caller_pbx_user_id'):
            generic_params['caller_pbx_user_id'] = int(
                cdr_data['caller_pbx_user_id'])
        if cdr_data.get('called_pbx_user_id'):
            generic_params['called_pbx_user_id'] = int(
                cdr_data['called_pbx_user_id'])

        channel = self.env['connect.channel'].process_channel_event(
            generic_params)
        call = self.process_call_event(channel)

        if channel:
            # Reverse orphan check: find channels that arrived before this one
            # and reference it as parent but couldn't link at the time
            orphan_channels = self.env['connect.channel'].search([
                ('parent_sid', '=', cdr_data['uuid']),
                ('parent_channel', '=', False),
                ('id', '!=', channel.id),
            ])
            for orphan in orphan_channels:
                orphan.parent_channel = channel
                if orphan.call and channel.call and orphan.call != channel.call:
                    old_call = orphan.call
                    orphan.call = channel.call
                    if not old_call.channels:
                        old_call.unlink()
                debug(self, 'Linked orphan channel %s to parent %s' % (
                    orphan.id, channel.id))

            # Link any recording that arrived before the CDR created the channel
            orphan_recordings = self.env['connect.recording'].search([
                ('call_sid', '=', cdr_data['uuid']),
                ('channel', '=', False),
            ])
            if orphan_recordings:
                orphan_recordings.write({
                    'channel': channel.id,
                    'call': channel.call.id if channel.call else False,
                    'partner': channel.partner.id if channel.partner else False,
                    'duration': channel.duration,
                    'caller_number': channel.caller_number,
                    'called_number': channel.called_number,
                })
                logger.info('Linked %d orphan recording(s) to channel %s',
                    len(orphan_recordings), cdr_data['uuid'])

        return call
