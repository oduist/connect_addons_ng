import hashlib
import logging
import re
from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.addons.connect.models.settings import debug
from odoo.addons.connect.models.call import CALL_END_STATUSES


def _bridge_lock_key(uuid, other_uuid):
    """Stable int64 key derived from the unordered pair of leg UUIDs.

    Used as a Postgres advisory lock to serialize CDR webhooks of two
    bridged legs across worker processes. Returns None when there is
    no second leg (no bridge => no race possible).
    """
    if not other_uuid:
        return None
    pair = ''.join(sorted([uuid, other_uuid]))
    digest = hashlib.md5(pair.encode()).digest()
    # int64 range; signed because pg_advisory_xact_lock takes bigint.
    return int.from_bytes(digest[:8], 'big', signed=True)

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

    fs_parked_slot = fields.Many2one(
        'connect.freeswitch.parking.slot',
        compute='_compute_fs_parked_slot', store=False,
        string='Parked On')

    def _compute_fs_parked_slot(self):
        Slot = self.env['connect.freeswitch.parking.slot']
        for rec in self:
            rec.fs_parked_slot = Slot.search(
                [('parked_call', '=', rec.id)], limit=1)

    def action_fs_park(self):
        """Park this call on the first available slot.

        Raises UserError if no free slot is configured.
        """
        self.ensure_one()
        if self.status in CALL_END_STATUSES:
            raise UserError("This call is already ended.")
        if self.fs_parked_slot:
            raise UserError(
                "This call is already parked on slot %s."
                % self.fs_parked_slot.exten)
        Slot = self.env['connect.freeswitch.parking.slot']
        slot = Slot.search(
            [('active', '=', True), ('parked_uuid', '=', False)],
            order='sequence, exten', limit=1)
        if not slot:
            raise UserError(
                "No free parking slots available. Configure additional "
                "slots under Connect → Configuration → Parking Slots.")
        return slot.action_park_call(self.id)

    @api.model
    def action_fs_park_by_uuid(self, uuid, slot_id=None):
        """Park a live call identified by a FreeSWITCH channel UUID.

        Invoked from the Verto phone widget which only knows its local
        Verto callId (the A-leg UUID). `connect.channel` records are
        only created at CDR (hangup), so we cannot rely on the DB
        during an active call — we ask FreeSWITCH directly for the
        bridged B-leg and caller identity, and park that leg on the
        requested slot (or the first free slot if none was specified).
        """
        Slot = self.env['connect.freeswitch.parking.slot']
        if slot_id:
            slot = Slot.browse(int(slot_id))
            if not slot.exists() or not slot.active:
                raise UserError("Selected parking slot is not available.")
        else:
            slot = Slot.search(
                [('active', '=', True), ('parked_uuid', '=', False)],
                order='sequence, exten', limit=1)
            if not slot:
                raise UserError("No free parking slots available.")
        return slot.action_park_channel_uuid(uuid)

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

        # Build a-leg (user's ringable endpoints + WebRTC)
        a_leg_parts = []

        # Display target number/partner on user's phone (a-leg caller ID)
        display_name = caller_name or number
        display_number = number

        # SIP endpoints with originate_ring enabled
        endpoints = self.env['connect.endpoint'].search([
            ('connect_user_id', '=', connect_user.id),
            ('active', '=', True),
            ('originate_ring', '=', True),
            ('auth_user', '!=', False),
        ])
        for ep in endpoints:
            leg_vars = [
                'leg_timeout=30',
                "origination_caller_id_name='{}'".format(
                    display_name.replace("'", "")),
                'origination_caller_id_number={}'.format(display_number),
            ]
            if ep.auto_answer_header:
                # Parse header: "Alert-Info:answer-after=0" → sip_h_Alert-Info=answer-after=0
                header_name, _, header_value = ep.auto_answer_header.partition(':')
                if header_name and header_value:
                    leg_vars.append('sip_h_{}={}'.format(
                        header_name.strip(), header_value.strip()))
            a_leg_parts.append(
                '[{}]user/{}@{}'.format(','.join(leg_vars), ep.auth_user, domain))

        # WebRTC (Verto) leg from user
        if connect_user.webrtc_enabled and connect_user.originate_ring:
            verto_login = connect_user.user.login
            a_leg_parts.append(
                "[leg_timeout=30,origination_caller_id_name='{name}'"
                ",origination_caller_id_number={num}"
                ",verto_h_auto_answer=true]user/{login}@{domain}".format(
                    name=display_name.replace("'", ""),
                    num=display_number,
                    login=verto_login,
                    domain=domain))

        if not a_leg_parts:
            raise UserError("You don't have any ringable endpoints configured.")

        a_leg = ','.join(a_leg_parts)

        # Caller ID for b-leg (what the called party sees)
        first_ep = endpoints[:1]
        caller_number = connect_user.exten_number or (first_ep.auth_user if first_ep else '')

        # Check if target is an internal extension
        exten = self.env['connect.exten'].search(
            [('number', '=', number)], limit=1)
        if exten:
            # Internal call — bridge to extension's destination
            b_leg = self._build_internal_b_leg(exten, domain)
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

    def _build_internal_b_leg(self, exten, domain):
        """Build b-leg bridge string for an internal extension."""
        # Check if extension points to a user
        if exten.model == 'connect.user' and exten.res_id:
            target_user = self.env['connect.user'].browse(exten.res_id)
            if target_user.exists() and target_user.active:
                return self._build_user_bridge(target_user, domain)

        # Check if extension points to a standalone endpoint
        if exten.model == 'connect.endpoint' and exten.res_id:
            target_ep = self.env['connect.endpoint'].browse(exten.res_id)
            if target_ep.exists() and target_ep.active and target_ep.auth_user:
                return 'user/{}@{}'.format(target_ep.auth_user, domain)

        # Fallback: bridge to the extension number directly
        return 'user/{}@{}'.format(exten.number, domain)

    def _build_user_bridge(self, target_user, domain):
        """Build bridge string for all of a user's active contacts."""
        b_parts = []

        # SIP endpoints (all active, not just originate_ring)
        target_endpoints = self.env['connect.endpoint'].search([
            ('connect_user_id', '=', target_user.id),
            ('active', '=', True),
            ('auth_user', '!=', False),
        ])
        for ep in target_endpoints:
            b_parts.append('user/{}@{}'.format(ep.auth_user, domain))

        # WebRTC
        if target_user.webrtc_enabled:
            b_parts.append('user/{}@{}'.format(
                target_user.user.login, domain))

        if b_parts:
            return ','.join(b_parts)

        # Fallback
        return 'user/{}@{}'.format(
            target_user.exten_number or '', domain)

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

        # Serialize bridged-pair CDRs across worker processes. mod_xml_cdr
        # POSTs each leg's CDR independently, and under Odoo's default
        # REPEATABLE READ isolation two overlapping transactions cannot
        # see each other's sibling rows — the result is two unlinked
        # channels and a duplicate connect.call. A transaction-scoped
        # advisory lock keyed by the sorted (uuid, other_leg_uuid) pair
        # makes the later worker wait, then take its snapshot AFTER the
        # earlier one commits, so the sibling lookup succeeds.
        lock_key = _bridge_lock_key(
            cdr_data['uuid'], cdr_data.get('other_leg_uuid'))
        if lock_key is not None:
            self.env.cr.execute(
                'SELECT pg_advisory_xact_lock(%s)', [lock_key])

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
