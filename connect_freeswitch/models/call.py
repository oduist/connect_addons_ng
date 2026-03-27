import logging
from odoo import models, api
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
