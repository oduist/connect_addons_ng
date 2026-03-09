import logging
import re
from odoo import fields, models, api, release
from .settings import debug

logger = logging.getLogger(__name__)


class Channel(models.Model):
    _name = 'connect.channel'
    _description = 'Channel'
    _inherit = 'mail.thread'
    _rec_name = 'id'
    _order = 'id desc'

    call = fields.Many2one('connect.call', ondelete='cascade')
    parent_channel = fields.Many2one('connect.channel', ondelete='cascade', tracking=True)
    parent_sid = fields.Char('Parent SID', tracking=True, readonly=True)
    partner = fields.Many2one('res.partner', ondelete='set null', tracking=True)
    called = fields.Char(tracking=True)
    to = fields.Char(tracking=True)
    technical_direction = fields.Char(tracking=True, string='Direction')
    status = fields.Char(tracking=True)
    duration = fields.Integer(string='Seconds', tracking=True)
    duration_minutes = fields.Float(string='Minutes', tracking=True)
    duration_billing = fields.Integer(string='Bill Minutes', tracking=True)
    duration_human = fields.Char(compute='_get_duration_human', string='Duration', store=True, tracking=True)
    caller = fields.Char(tracking=True)
    call_type = fields.Selection([
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp')
    ], default='phone', index=True, tracking=True)
    caller_pbx_user = fields.Many2one('connect.user', ondelete='set null', string='Caller PBX User', tracking=True)
    called_pbx_user = fields.Many2one('connect.user', ondelete='set null', string='Called PBX User', tracking=True)
    caller_user = fields.Many2one('res.users', string='Caller User', tracking=True)
    called_user = fields.Many2one('res.users', string='Called User', tracking=True)
    caller_number = fields.Char(compute='_get_channel_numbers', store=True, index=True)
    called_number = fields.Char(compute='_get_channel_numbers', store=True, index=True)

    @api.depends('caller', 'called')
    def _get_channel_numbers(self):
        re_number_domain = re.compile(r'^(sip|client):(.+)@(.+)$')
        re_client_number = re.compile(r'^client:(\d{8})$')
        re_number = re.compile(r'^(\+?[0-9]+)$')
        re_whatsapp = re.compile(r'^whatsapp:(\+?[0-9]+)$')

        def _get_number(callinfo):
            if not isinstance(callinfo, str):
                return ''
            if re_number.search(callinfo):
                return callinfo
            elif re_whatsapp.search(callinfo):
                return re_whatsapp.search(callinfo).group(1)
            elif re_number_domain.search(callinfo):
                user_or_number = re_number_domain.search(callinfo).group(2)
                user = self.env['connect.user'].get_user_by_uri(callinfo)
                if user:
                    return user.exten.number
                else:
                    return user_or_number
            elif re_client_number.search(callinfo):
                return re_client_number.search(callinfo).group(1)
            else:
                return ''

        for rec in self:
            rec.caller_number = _get_number(rec.caller)
            rec.called_number = _get_number(rec.called)

    @api.depends('duration')
    def _get_duration_human(self):
        for record in self:
            if record.duration is not None:
                minutes = record.duration // 60
                seconds = record.duration % 60
                record.duration_human = '{:02}:{:02}'.format(minutes, seconds)
                record.duration_minutes = record.duration / 60.0
            else:
                record.duration_minutes = 0
                record.duration_human = "00:00"
