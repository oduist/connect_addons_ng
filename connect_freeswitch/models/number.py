import logging
import re
from xml.sax.saxutils import escape as xml_escape

from odoo import api, fields, models

logger = logging.getLogger(__name__)


class Number(models.Model):
    _name = 'connect.freeswitch.number'
    _description = 'FreeSWITCH Phone Number'
    _rec_name = 'phone_number'
    _order = 'phone_number'

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
    # Working schedule (issue #57, ADR-037): when enabled, the fields
    # above act as the "available" destination and the closed_* fields
    # take over outside of working hours.
    schedule_enabled = fields.Boolean('Use Working Schedule')
    schedule_id = fields.Many2one(
        'connect.schedule', string='Working Schedule', ondelete='restrict')
    closed_destination = fields.Selection(selection=[
        ('user', 'User'),
        ('callflow', 'CallFlow'),
        ('fs_fifo', 'FS Queue'),
    ], string='Destination (Unavailable)', ondelete='set null')
    closed_user = fields.Many2one(
        'connect.user', string='User (Unavailable)', ondelete='set null')
    closed_callflow = fields.Many2one(
        'connect.freeswitch.callflow', string='CallFlow (Unavailable)',
        ondelete='set null')
    closed_fs_fifo_id = fields.Many2one(
        'connect.fs_fifo', string='FS Queue (Unavailable)',
        ondelete='set null')
    schedule_prompt_language = fields.Selection(
        selection=lambda self: self.env[
            'connect.freeswitch.callflow']._get_language_selection(),
        string='Prompt Language', default='en-US',
        help='Piper TTS language used to play the public holiday prompt '
             'message to callers.')

    def write(self, vals):
        if 'destination' in vals:
            mapping = {'user': 'user', 'callflow': 'callflow', 'fs_fifo': 'fs_fifo_id'}
            keep = mapping.get(vals['destination'])
            for field in mapping.values():
                if field != keep:
                    vals.setdefault(field, False)
        if 'closed_destination' in vals:
            mapping = {
                'user': 'closed_user',
                'callflow': 'closed_callflow',
                'fs_fifo': 'closed_fs_fifo_id',
            }
            keep = mapping.get(vals['closed_destination'])
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

    def action_view_schedule_slots(self):
        self.ensure_one()
        return self.schedule_id.action_view_slots()

    @api.model
    def _get_transfer_target(self, destination, user, callflow, fifo):
        if destination == 'user' and user:
            return user.freeswitch_exten_number
        elif destination == 'callflow' and callflow:
            return callflow.exten_number or str(callflow.id)
        elif destination == 'fs_fifo' and fifo:
            return fifo.exten_number or str(fifo.id)
        return ''

    def generate_dialplan(self, params):
        """Generate FreeSWITCH dialplan XML for inbound DID routing."""
        self.ensure_one()

        destination, user, callflow, fifo = (
            self.destination, self.user, self.callflow, self.fs_fifo_id)
        schedule_prompt = ''
        if self.schedule_enabled and self.schedule_id:
            status = self.schedule_id.sudo().get_status()
            if not status['available']:
                destination, user, callflow, fifo = (
                    self.closed_destination, self.closed_user,
                    self.closed_callflow, self.closed_fs_fifo_id)
                if status['prompt_message']:
                    schedule_prompt = xml_escape(
                        status['prompt_message'], {'"': '&quot;'})
        transfer_target = self._get_transfer_target(
            destination, user, callflow, fifo)

        # Match the destination_number FreeSWITCH presents, which may arrive
        # with or without the leading '+'. Anchor on the bare digits and make
        # the '+' optional so either trunk format routes to the same DID.
        # See specs/decisions/023-inbound-did-format-normalization.md.
        raw = self.phone_number or ''
        digits = raw[1:] if raw.startswith('+') else raw
        number_regex = r'\+?' + re.escape(digits)
        caller_name = ''
        caller_number = params.get('Caller-Caller-ID-Number') or params.get(
            'caller_id_number')
        if caller_number:
            partner = self.env['res.partner'].get_partner_by_number(
                caller_number)
            caller_name = partner.display_name if partner else ''

        return self.env['connect.freeswitch.template'].render('dialplan_inbound_did', {
            'number_regex': number_regex,
            'did_label': digits,
            'phone_number': raw,
            'number_id': self.id,
            'destination': destination,
            'transfer_target': transfer_target,
            'caller_name': caller_name,
            'schedule_prompt': schedule_prompt,
            'schedule_prompt_lang': self.schedule_prompt_language or 'en-US',
        })
