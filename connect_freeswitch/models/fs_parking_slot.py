import logging
import re

from odoo import api, fields, models, release
from odoo.exceptions import UserError
from odoo.models import Constraint

logger = logging.getLogger(__name__)

PARKING_LOT_NAME = 'default'


class FreeSwitchParkingSlot(models.Model):
    _name = 'connect.freeswitch.parking.slot'
    _description = 'FreeSWITCH Parking Slot'
    _order = 'sequence, exten'

    name = fields.Char(required=True)
    exten = fields.Char(
        string='Extension',
        required=True,
        index=True,
        help="Dialable slot number. SIP phones subscribe to <exten>@domain for BLF. "
             "Dialing this extension parks (if free) or retrieves (if occupied).",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    parked_call = fields.Many2one(
        'connect.call', readonly=True, ondelete='set null',
        string='Parked Call')
    parked_at = fields.Datetime(readonly=True)
    parked_by_user = fields.Many2one(
        'res.users', readonly=True, ondelete='set null',
        string='Parked By')
    parked_caller_number = fields.Char(readonly=True)
    parked_caller_name = fields.Char(readonly=True)
    parked_uuid = fields.Char(readonly=True, string='FreeSWITCH UUID')

    is_occupied = fields.Boolean(
        compute='_compute_is_occupied', store=True)

    _exten_unique = Constraint(
        'unique(exten)',
        'A parking slot with this extension already exists.',
    )

    @api.depends('parked_uuid')
    def _compute_is_occupied(self):
        for rec in self:
            rec.is_occupied = bool(rec.parked_uuid)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_park_call(self, call_id=None):
        """Park the given connect.call on this slot.

        Transfers the remote leg to the slot extension in dialplan
        context ``default`` so the ``connect_valet_parking_<slot>``
        extension runs — setting ``api_hangup_hook`` (for the
        ``released`` webhook) and firing the ``entered`` webhook before
        ``valet_park``. An ``inline`` transfer would bypass the
        dialplan and the hooks would never fire.
        """
        self.ensure_one()
        if self.is_occupied:
            raise UserError(
                "Slot %s is already occupied." % self.exten)
        call = self.env['connect.call'].browse(call_id) if call_id else self.env['connect.call']
        if not call.exists():
            raise UserError("Call not found.")

        uuid = self._find_remote_leg_uuid(call)
        if not uuid:
            raise UserError(
                "Cannot find an active channel for this call. "
                "Make sure the call is still in progress.")

        settings = self.env['connect.settings']
        args = "{uuid} {slot} XML default".format(uuid=uuid, slot=self.exten)
        result = settings.freeswitch_api('uuid_transfer', args)
        if not result or str(result).startswith('-ERR'):
            raise UserError(
                "FreeSWITCH rejected the park: %s" % (result or 'no response'))

        self.sudo().write({
            'parked_call': call.id,
            'parked_uuid': uuid,
            'parked_at': fields.Datetime.now(),
            'parked_by_user': self.env.user.id,
            'parked_caller_number': call.caller or '',
            'parked_caller_name': call.partner.name if call.partner else '',
        })
        self._notify_bus()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Call Parked',
                'message': 'Call parked on slot %s' % self.exten,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_park_channel_uuid(self, uuid):
        """Park the bridged remote leg of a live FS channel on this slot.

        Resolves the remote leg via `uuid_getvar <uuid> bridge_uuid`
        since `connect.channel` records do not exist until CDR arrives.
        """
        self.ensure_one()
        if self.is_occupied:
            raise UserError("Slot %s is already occupied." % self.exten)
        if not uuid:
            raise UserError("No channel UUID provided.")

        settings = self.env['connect.settings']
        remote_uuid = self._resolve_remote_leg(uuid, settings) or uuid

        args = "{uuid} {slot} XML default".format(
            uuid=remote_uuid, slot=self.exten)
        result = settings.freeswitch_api('uuid_transfer', args)
        if not result or str(result).startswith('-ERR'):
            raise UserError(
                "FreeSWITCH rejected the park: %s" % (result or 'no response'))

        caller_number = self._get_channel_var(
            remote_uuid, 'caller_id_number', settings)
        caller_name = self._get_channel_var(
            remote_uuid, 'caller_id_name', settings)
        channel = self.env['connect.channel'].sudo().search(
            [('sid', '=', remote_uuid)], limit=1)

        self.sudo().write({
            'parked_call': channel.call.id if channel and channel.call else False,
            'parked_uuid': remote_uuid,
            'parked_at': fields.Datetime.now(),
            'parked_by_user': self.env.user.id,
            'parked_caller_number': caller_number or '',
            'parked_caller_name': caller_name or '',
        })
        self._notify_bus()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Call Parked',
                'message': 'Call parked on slot %s' % self.exten,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_reset(self):
        """Forcefully clear slot state.

        Used when Odoo and FreeSWITCH fall out of sync (e.g. a park
        transfer failed after we optimistically wrote the slot). Does
        not touch FS — the channel, if any, is untouched.
        """
        for rec in self:
            rec.sudo().write({
                'parked_uuid': False,
                'parked_call': False,
                'parked_at': False,
                'parked_by_user': False,
                'parked_caller_number': False,
                'parked_caller_name': False,
            })
            rec._notify_bus()
        return True

    def action_sync_from_fs(self):
        """Drop state for slots not actually parked in FreeSWITCH.

        Queries `valet_info <lot>` for the authoritative list of
        currently-parked UUIDs. `uuid_exists` is not enough: after
        retrieval the channel is still alive (bridged to the new leg)
        but no longer in the lot, so the slot must be cleared.
        """
        settings = self.env['connect.settings']
        live = self._fetch_parked_uuids(settings)
        targets = self or self.sudo().search(
            [('active', '=', True), ('parked_uuid', '!=', False)])
        cleared = 0
        for slot in targets:
            if not slot.parked_uuid:
                continue
            if slot.parked_uuid not in live:
                slot.action_reset()
                cleared += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Parking Sync',
                'message': ('%d stale slot(s) cleared.' % cleared
                            if cleared else 'All slots in sync.'),
                'type': 'info',
                'sticky': False,
            },
        }

    def action_unpark(self):
        """Retrieve the parked call by originating to the requesting user
        and bridging into the slot's valet extension."""
        self.ensure_one()
        if not self.is_occupied:
            raise UserError("Slot %s is empty." % self.exten)

        user = self.env.user
        connect_user = self.env['connect.user'].search([
            ('user', '=', user.id),
            ('active', '=', True),
        ], limit=1)
        if not connect_user:
            raise UserError("You don't have a Connect user configured.")

        settings = self.env['connect.settings']
        domain = self.env['connect.settings'].sudo()._get().freeswitch_domain
        if not domain:
            raise UserError("FreeSWITCH domain is not configured.")

        endpoint_parts = self.env['connect.call']._build_user_bridge(
            connect_user, domain)
        if not endpoint_parts:
            raise UserError("You don't have any ringable endpoints.")

        cid_name = (self.parked_caller_name or self.parked_caller_number or
                    'Slot %s' % self.exten).replace("'", "")
        cid_num = self.parked_caller_number or self.exten
        variables = [
            "origination_caller_id_name='{}'".format(cid_name),
            "origination_caller_id_number={}".format(cid_num),
            'ignore_early_media=true',
        ]
        if connect_user.webrtc_enabled:
            variables.append('verto_h_auto_answer=true')
        cmd = "{{{}}}{} '&valet_park({} {})'".format(
            ','.join(variables), endpoint_parts,
            PARKING_LOT_NAME, self.exten)
        logger.info("Unpark slot %s: originate %s", self.exten, cmd)

        result = settings.freeswitch_api('originate', cmd)
        logger.info("Unpark slot %s: FS result: %r", self.exten, result)
        if not result or str(result).startswith('-ERR'):
            raise UserError(
                "FreeSWITCH rejected the unpark: %s" % (result or 'no response'))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Retrieving Call',
                'message': 'Ringing your phone to pick up slot %s' % self.exten,
                'type': 'info',
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------
    # Webhook entry points (called from controllers/freeswitch_parking.py)
    # ------------------------------------------------------------------

    @api.model
    def on_parking_entered(self, exten, uuid, caller_number='', caller_name=''):
        """A channel has entered the valet lot on the given slot."""
        slot = self.sudo().search([('exten', '=', exten)], limit=1)
        if not slot:
            logger.warning("Parking webhook: unknown slot %s", exten)
            return False

        # Idempotent: if same UUID already recorded, ignore.
        if slot.parked_uuid == uuid:
            return True

        channel = self.env['connect.channel'].sudo().search(
            [('sid', '=', uuid)], limit=1)
        call = channel.call if channel else self.env['connect.call']

        slot.write({
            'parked_uuid': uuid,
            'parked_call': call.id if call else False,
            'parked_at': fields.Datetime.now(),
            'parked_caller_number': caller_number or (call.caller if call else ''),
            'parked_caller_name': caller_name or (call.partner.name if call and call.partner else ''),
        })
        slot._notify_bus()
        return True

    @api.model
    def on_parking_released(self, exten):
        """A parked channel left the lot (retrieved or hung up)."""
        slot = self.sudo().search([('exten', '=', exten)], limit=1)
        if not slot:
            return False
        if not slot.parked_uuid:
            return True
        slot.write({
            'parked_uuid': False,
            'parked_call': False,
            'parked_at': False,
            'parked_by_user': False,
            'parked_caller_number': False,
            'parked_caller_name': False,
        })
        slot._notify_bus()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_parked_uuids(self, settings):
        """Return the set of UUIDs currently parked in our lot.

        `valet_info <lot>` returns XML like::

            <lots>
              <lot name="default">
                <extension uuid="...">705</extension>
              </lot>
            </lots>

        Empty lot → no <extension> elements; FS unreachable → empty set
        (caller must interpret this as "don't know, leave Odoo state as is"
        — but action_sync_from_fs intentionally treats empty as "clear",
        matching what operators expect when FS has been restarted).
        """
        raw = settings.freeswitch_api('valet_info', PARKING_LOT_NAME)
        if not raw:
            return set()
        return set(re.findall(r'uuid="([^"]+)"', str(raw)))

    def _resolve_remote_leg(self, uuid, settings):
        """Ask FreeSWITCH for the UUID bridged to `uuid`.

        Returns the bridge_uuid if the channel is bridged to another leg
        (the common case: park the far side, not the widget's own leg).
        Returns False if the channel has no bridge or FS is unreachable.
        """
        bridge = settings.freeswitch_api(
            'uuid_getvar', '%s bridge_uuid' % uuid)
        if not bridge:
            return False
        bridge = str(bridge).strip()
        if not bridge or bridge.startswith('-') or bridge == '_undef_':
            return False
        return bridge

    def _get_channel_var(self, uuid, var, settings):
        """Read a channel variable via FS API; empty string on failure."""
        val = settings.freeswitch_api('uuid_getvar', '%s %s' % (uuid, var))
        if not val:
            return ''
        val = str(val).strip()
        if val.startswith('-') or val == '_undef_':
            return ''
        return val

    def _find_remote_leg_uuid(self, call):
        """Return UUID of the channel NOT belonging to the current user.

        Picks active (not ended) channels first; falls back to the latest
        channel if none are marked active.
        """
        from odoo.addons.connect.models.call import CALL_END_STATUSES
        me = self.env.user
        connect_me = self.env['connect.user'].search(
            [('user', '=', me.id)], limit=1)
        channels = call.channels.sorted('id', reverse=True)
        for ch in channels:
            if ch.status in CALL_END_STATUSES:
                continue
            if connect_me and ch.caller_pbx_user == connect_me:
                continue
            if ch.sid:
                return ch.sid
        # Fallback: any channel with a sid
        for ch in channels:
            if ch.sid:
                return ch.sid
        return False

    def _notify_bus(self):
        """Push a reload signal so every Verto widget refreshes its panel."""
        payload = {
            'id': self.id,
            'exten': self.exten,
            'is_occupied': self.is_occupied,
        }
        if release.version_info[0] < 15:
            import json
            self.env['bus.bus'].sendone(
                'connect_actions',
                json.dumps({'action': 'parking_state_changed', 'payload': payload}))
        else:
            self.env['bus.bus']._sendone(
                'connect_actions', 'parking_state_changed', payload)
