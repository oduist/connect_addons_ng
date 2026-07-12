import logging
import re
from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.addons.connect.models.settings import debug
from odoo.addons.connect.models.call import CALL_END_STATUSES

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
        # The number is interpolated into the FreeSWITCH originate
        # dialstring (channel variables and bridge data) via str.format,
        # so it must not carry originate metacharacters ({}[]<>,&'|" etc.).
        # Restrict to an optional leading '+' followed by digits and the
        # DTMF feature-code characters '*'/'#' (ADR-026).
        if not re.fullmatch(r'\+?[0-9*#]{1,20}', number):
            raise UserError("Invalid phone number: {}".format(number))

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
        endpoints = self.env['connect.freeswitch.endpoint'].search([
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

        # WebRTC (Verto) leg from user.
        # The Verto contact is addressed by the user's Verto login
        # (<login-local><res.users.id>), matching the FS XML directory. See
        # specs/decisions/016-verto-login-uses-user-id.md.
        if connect_user.webrtc_enabled and connect_user.originate_ring \
                and connect_user.user:
            verto_login = connect_user._get_verto_login()
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

        # Check if target is an internal extension
        exten = self.env['connect.freeswitch.exten'].search(
            [('number', '=', number)], limit=1)

        # Caller ID for b-leg (what the called party sees)
        first_ep = endpoints[:1]
        if exten:
            caller_number = connect_user.freeswitch_exten_number or (first_ep.auth_user if first_ep else '')
        else:
            # Per-user outgoing CallerID, else the system-wide default DID
            # (is_default), else the extension — symmetric with the Twilio
            # path and the UA-originated dialplan override (ADR-027, #96).
            default_cid = self.env['connect.freeswitch.outgoing_callerid'].sudo().search(
                [('is_default', '=', True)], limit=1)
            caller_number = (
                connect_user.freeswitch_outgoing_callerid.number
                or default_cid.number
                or connect_user.freeswitch_exten_number
                or (first_ep.auth_user if first_ep else '')
            )

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
        cid_name = (caller_name or caller_number).replace("'", "")
        variables = [
            "origination_caller_id_name='{}'".format(cid_name),
            "origination_caller_id_number={}".format(caller_number),
            "odoo_caller_pbx_user_id={}".format(connect_user.id),
            # `originate user/<login>@<domain>` makes the A-leg's
            # caller_profile.destination_number the resolved user URI
            # (e.g. "u:<verto-uuid>"), not the dialled number. Stash
            # the real destination so the CDR parser can recover it.
            "odoo_destination_number={}".format(number),
            # The A-leg goes through the user directory, which seeds
            # effective_caller_id_* from the user's extension and
            # silently overrides any globals we try to set. Stash the
            # intended caller-id on a custom variable that the CDR
            # parser can pick up — symmetric with the dialplan SET
            # that UA-originated calls do via ADR-021.
            "odoo_caller_id_name='{}'".format(cid_name),
            "odoo_caller_id_number={}".format(caller_number),
        ]
        if partner_id:
            variables.append("odoo_partner_id={}".format(partner_id))

        # B-leg caller-id: the bridge subchannel that actually reaches
        # the PSTN gateway (or the called user for internal calls)
        # inherits its caller-id from the A-leg by default, which is
        # the directory-seeded extension. Override on the B-leg itself
        # so the called party sees `caller_number` (extension for
        # internal, outgoing_callerid for external).
        #
        # For external (PSTN) calls the display NAME is blanked so the
        # internal caller's name is never disclosed to the outside world;
        # only the number is sent. Internal calls keep the name so the
        # colleague sees who is ringing. See ADR-026.
        b_leg_name = cid_name if exten else ''
        b_leg_vars = [
            "origination_caller_id_name='{}'".format(b_leg_name),
            "origination_caller_id_number={}".format(caller_number),
        ]
        # For external calls via gateway, force standard codecs on b-leg
        # since a-leg may be WebRTC (Opus) which gateways don't support
        if not exten:
            b_leg_vars.append("absolute_codec_string=PCMU,PCMA")
        b_leg = '[{}]{}'.format(','.join(b_leg_vars), b_leg)

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
        if exten.model == 'connect.freeswitch.endpoint' and exten.res_id:
            target_ep = self.env['connect.freeswitch.endpoint'].browse(exten.res_id)
            if target_ep.exists() and target_ep.active and target_ep.auth_user:
                return 'user/{}@{}'.format(target_ep.auth_user, domain)

        # Fallback: bridge to the extension number directly
        return 'user/{}@{}'.format(exten.number, domain)

    def _build_user_bridge(self, target_user, domain):
        """Build bridge string for all of a user's active contacts."""
        b_parts = []

        # SIP endpoints (all active, not just originate_ring)
        target_endpoints = self.env['connect.freeswitch.endpoint'].search([
            ('connect_user_id', '=', target_user.id),
            ('active', '=', True),
            ('auth_user', '!=', False),
        ])
        for ep in target_endpoints:
            b_parts.append('user/{}@{}'.format(ep.auth_user, domain))

        # WebRTC: address the Verto contact by the user's Verto login
        # (<login-local><res.users.id>), matching the FS XML directory.
        # See specs/decisions/016-verto-login-uses-user-id.md.
        if target_user.webrtc_enabled and target_user.user:
            b_parts.append('user/{}@{}'.format(
                target_user._get_verto_login(), domain))

        if b_parts:
            return ','.join(b_parts)

        # Fallback
        return 'user/{}@{}'.format(
            target_user.freeswitch_exten_number or '', domain)

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
                odoo_call_direction (str): dialplan-stamped business
                    direction, 'inbound' or 'outgoing' (optional; preferred
                    over the native FreeSWITCH `direction` when present)

        Returns:
            call id or False
        """
        self = self.sudo()
        debug(self, 'FreeSWITCH CDR: %s' % cdr_data)

        # Serialize sibling legs of the same bridge. odoo_chain_id is
        # exported in the dialplan (no `nolocal:`) so both legs share the
        # same value — the A-leg's uuid at bridge time.
        #
        # Session-scoped pg_advisory_lock (not xact-scoped): Odoo runs under
        # REPEATABLE READ, and the snapshot is taken when the acquiring
        # SELECT starts, *before* it blocks. Session-scoped lets us commit
        # after acquiring (refreshing the snapshot) while the lock persists.
        #
        # Critical: we must commit *our own* work before releasing the lock,
        # otherwise the sibling acquires the lock and snapshots before the
        # http handler's outer commit has flushed our writes.
        chain_key = cdr_data.get('chain_id') or cdr_data['uuid']
        self.env.cr.commit()  # drop stale snapshot from controller entry
        self.env.cr.execute(
            "SELECT pg_advisory_lock(hashtext(%s))", [chain_key])
        self.env.cr.commit()  # end the acquire-tx so the next read is fresh
        self.env.invalidate_all()  # flush ORM caches tied to the old snapshot
        try:
            result = self._process_cdr_locked(cdr_data)
            self.env.cr.commit()  # commit BEFORE unlocking so sibling sees our writes
            return result
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", [chain_key])

    @api.model
    def _cdr_technical_direction(self, cdr_data):
        """Resolve the Twilio-compatible technical_direction for a CDR.

        Prefer the business-logic direction the dialplan stamps on the
        channel (`odoo_call_direction`) over FreeSWITCH's per-leg native
        direction. originate-launched legs and the UA leg of an outgoing
        call are `inbound` from FreeSWITCH's own perspective and would
        otherwise be mislabelled as incoming (issue #43). Fall back to the
        native direction when the variable is absent (e.g. a raw originate
        that bypasses the dialplan).
        """
        odoo_direction = cdr_data.get('odoo_call_direction')
        if odoo_direction == 'outgoing':
            return 'outbound-api'
        if odoo_direction == 'inbound':
            return 'inbound'
        return (
            'outbound-api'
            if cdr_data.get('direction') == 'outbound'
            else 'inbound'
        )

    @api.model
    def _process_cdr_locked(self, cdr_data):
        """Inner CDR processing, called while holding the chain lock."""
        status = HANGUP_CAUSE_MAP.get(
            cdr_data.get('hangup_cause', ''), 'failed')

        # Map the call direction to a Twilio-compatible technical_direction,
        # preferring the dialplan-stamped odoo_call_direction (issue #43).
        technical_direction = self._cdr_technical_direction(cdr_data)

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
            number = self.env['connect.freeswitch.number'].browse(odoo_number_id).exists()
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
                    # Use a fresh DB count instead of `old_call.channels`
                    # because the One2many cache is not invalidated by
                    # the inverse-side write above and still reports the
                    # moved channel as belonging to old_call.
                    remaining = self.env['connect.channel'].sudo().search_count(
                        [('call', '=', old_call.id)])
                    if not remaining:
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
                voicemail_recordings = orphan_recordings.filtered(
                    lambda rec: rec.source == 'freeswitch_voicemail'
                    and rec.recording_attachment
                    and rec.call)
                if voicemail_recordings:
                    recording = max(voicemail_recordings, key=lambda rec: rec.id)
                    recording.call.write({
                        'voicemail_url': recording.get_attachment_media_url(),
                        'voicemail_duration': recording.duration or 0,
                    })
                logger.info('Linked %d orphan recording(s) to channel %s',
                    len(orphan_recordings), cdr_data['uuid'])

        return call
