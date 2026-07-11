import logging
import re
from odoo import api, fields, models

logger = logging.getLogger(__name__)


class Number(models.Model):
    _name = 'connect.freeswitch.number'
    _description = 'FreeSWITCH Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

    is_default = fields.Boolean(string='Default')
    phone_number = fields.Char(required=True)
    friendly_name = fields.Char()
    destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
        ('fs_fifo', 'FS Queue'),
    ], ondelete='set null')
    callflow = fields.Many2one('connect.freeswitch.callflow', ondelete='set null')
    user = fields.Many2one('connect.user', ondelete='set null')
    fs_fifo_id = fields.Many2one(
        'connect.fs_fifo', string='FS Queue', ondelete='set null')

    def write(self, vals):
        if 'destination' in vals:
            mapping = {'user': 'user', 'callflow': 'callflow', 'fs_fifo': 'fs_fifo_id'}
            keep = mapping.get(vals['destination'])
            for field in mapping.values():
                if field != keep:
                    vals.setdefault(field, False)
        return super().write(vals)

    @api.model
    def _find_by_did(self, destination):
        """Find the number record for an inbound destination, tolerating an
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
        if self.destination == 'user' and self.user:
            transfer_target = self.user.freeswitch_exten_number
        elif self.destination == 'callflow' and self.callflow:
            transfer_target = self.callflow.exten_number or str(self.callflow.id)
        elif self.destination == 'fs_fifo' and self.fs_fifo_id:
            transfer_target = self.fs_fifo_id.exten_number or str(self.fs_fifo_id.id)

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
            'destination': self.destination,
            'transfer_target': transfer_target,
        })
