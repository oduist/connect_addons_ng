import logging
import re
from odoo import api, fields, models

logger = logging.getLogger(__name__)


class Number(models.Model):
    _inherit = 'connect.number'

    fs_fifo_id = fields.Many2one(
        'connect.fs_fifo', string='FS Queue', ondelete='set null')

    def write(self, vals):
        # ODU-12: when destination switches away from the FS provider, clear
        # the FS-specific destination pointer. The selection_add of
        # 'fs_fifo' on `destination` is gone — FS routes now via
        # destination='provider' + destination_provider_id == freeswitch.
        if 'destination_provider_id' in vals or 'destination' in vals:
            current_provider = vals.get('destination_provider_id', None)
            if vals.get('destination') and vals['destination'] != 'provider':
                vals.setdefault('fs_fifo_id', False)
            elif current_provider is False:
                vals.setdefault('fs_fifo_id', False)
        return super().write(vals)

    def _is_freeswitch_destination(self):
        return (self.destination == 'provider'
                and self.destination_provider_id
                and self.destination_provider_id.code == 'freeswitch')

    @api.model
    def _find_by_did(self, destination):
        """Find the connect.number for an inbound destination, tolerating an
        optional leading '+' mismatch between the trunk format and the stored
        DID (e.g. trunk sends ``41215121140`` while the DID is stored as
        ``+41215121140`` or vice-versa). Exact match wins; only if none is
        found do we try the toggled-'+' form."""
        if not destination:
            return self.browse()
        number = self.search([('phone_number', '=', destination)], limit=1)
        if not number:
            alt = destination[1:] if destination.startswith('+') else '+' + destination
            number = self.search([('phone_number', '=', alt)], limit=1)
        return number

    def generate_dialplan(self, params):
        """Generate FreeSWITCH dialplan XML for inbound DID routing."""
        self.ensure_one()

        transfer_target = ''
        # `destination` reported to FS template kept as a friendly tag —
        # 'fs_fifo' is the legacy tag the dialplan branches on.
        dest_tag = self.destination
        if self.destination == 'user' and self.user:
            transfer_target = self.user.exten_number
        elif self.destination == 'callflow' and self.callflow:
            transfer_target = self.callflow.exten_number or str(self.callflow.id)
        elif self._is_freeswitch_destination() and self.fs_fifo_id:
            transfer_target = self.fs_fifo_id.exten_number or str(self.fs_fifo_id.id)
            dest_tag = 'fs_fifo'

        # Match the destination_number FreeSWITCH presents, which may arrive
        # with or without the leading '+'. Anchor on the bare digits and make
        # the '+' optional so either trunk format routes to the same DID.
        # See specs/decisions/023-inbound-did-format-normalization.md.
        raw = self.phone_number or ''
        digits = raw[1:] if raw.startswith('+') else raw
        number_regex = r'\+?' + re.escape(digits)

        return self.env['connect.freeswitch.template'].render('dialplan_inbound_did', {
            'number_regex': number_regex,
            'did_label': digits,
            'phone_number': raw,
            'number_id': self.id,
            'destination': dest_tag,
            'transfer_target': transfer_target,
        })
