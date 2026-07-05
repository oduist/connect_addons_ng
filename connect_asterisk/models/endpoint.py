# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .passphrase import generate_passphrase

# When click-to-call originates a call, Asterisk first dials the user's own
# phone (the first leg) and only after answer dials the destination. The
# first leg can be auto-answered with a SIP header; different phone models
# expect different headers.
AUTO_ANSWER_HEADERS = [
    ('Alert-Info:answer-after=0', 'Alert-Info:answer-after=0'),
    ('Alert-Info: Info=Alert-Autoanswer', 'Alert-Info: Info=Alert-Autoanswer'),
    ('Alert-Info: Info=Auto Answer', 'Alert-Info: Info=Auto Answer'),
    ('Alert-Info: ;info=alert-autoanswer', 'Alert-Info: ;info=alert-autoanswer'),
    ('Alert-Info: <sip:>;info=alert-autoanswer', 'Alert-Info: <sip:>;info=alert-autoanswer'),
    ('Alert-Info: Ring Answer', 'Alert-Info: Ring Answer'),
    ('Answer-Mode: Auto', 'Answer-Mode: Auto'),
    ('Call Info: Answer-After=0', 'Call Info: Answer-After=0'),
    ('Call-Info: Auto Answer', 'Call-Info: Auto Answer'),
    ('Call-Info: <sip:>;answer-after=0', 'Call-Info: <sip:>;answer-after=0'),
    ('P-Auto-Answer: normal', 'P-Auto-Answer: normal'),
]

SIP_TRANSPORT_SELECTION = [
    ('udp', 'UDP'),
    ('tcp', 'TCP'),
    ('webrtc', 'WebRTC'),
]


class ConnectEndpoint(models.Model):
    _inherit = 'connect.endpoint'

    asterisk_channel = fields.Char(
        string='Asterisk Channel',
        help='Asterisk dial string of this endpoint, e.g. PJSIP/101. '
             'Used to match AMI channel events to this endpoint and to '
             'originate click-to-call calls.')
    asterisk_sip_user = fields.Char(
        string='Asterisk SIP User',
        compute='_compute_asterisk_sip_user', store=True,
        help='SIP username derived from the Asterisk channel '
             '(PJSIP/101 → 101).')
    asterisk_sip_password = fields.Char(
        string='Asterisk SIP Password',
        readonly=True, copy=False,
        groups='connect.group_admin',
        help='SIP credential. Auto-generated as a typeable passphrase. '
             'Read-only and auto-managed — use the Regenerate button to '
             'issue a new one. Exposed to the owning user only through '
             'the web phone configuration.')
    asterisk_sip_transport = fields.Selection(
        selection=SIP_TRANSPORT_SELECTION,
        string='Asterisk SIP Transport',
        default='udp')
    asterisk_originate_enabled = fields.Boolean(
        string='Asterisk Originate', default=True,
        help='Dial this endpoint when click-to-call is used.')
    asterisk_originate_context = fields.Char(
        string='Asterisk Context',
        help='Dialplan context for click-to-call. Falls back to the '
             'Originate Context from Connect Settings → Asterisk.')
    asterisk_auto_answer_header = fields.Selection(
        selection=AUTO_ANSWER_HEADERS,
        string='Asterisk Auto-Answer Header',
        help='SIP header sent to auto-answer the phone during '
             'click-to-call originate.')

    @api.depends('asterisk_channel')
    def _compute_asterisk_sip_user(self):
        for rec in self:
            if rec.asterisk_channel and '/' in rec.asterisk_channel:
                rec.asterisk_sip_user = rec.asterisk_channel.split('/')[1]
            else:
                rec.asterisk_sip_user = rec.asterisk_channel or False

    @api.constrains('asterisk_channel')
    def _check_asterisk_channel(self):
        for rec in self:
            if not rec.asterisk_channel:
                continue
            if ' ' in rec.asterisk_channel:
                raise ValidationError('Spaces are not allowed in the channel!')
            if not re.match(r'^[A-Za-z0-9]+/[^/]+$', rec.asterisk_channel):
                raise ValidationError(
                    'Bad channel format. Example: PJSIP/101.')
            duplicate = self.sudo().with_context(active_test=False).search([
                ('asterisk_channel', '=', rec.asterisk_channel),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    'Channel {} is already defined on endpoint {}!'.format(
                        rec.asterisk_channel, duplicate.name))

    @api.onchange('asterisk_sip_transport')
    def _onchange_asterisk_sip_transport(self):
        if (not self.asterisk_auto_answer_header
                and self.asterisk_sip_transport == 'webrtc'):
            self.asterisk_auto_answer_header = 'Answer-Mode: Auto'

    def action_regenerate_asterisk_sip_password(self):
        """Issue a fresh auto-generated passphrase for the SIP credential."""
        for record in self:
            record.asterisk_sip_password = generate_passphrase()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('asterisk_channel') and not vals.get(
                    'asterisk_sip_password'):
                vals['asterisk_sip_password'] = generate_passphrase()
        return super().create(vals_list)

    @api.model
    def get_endpoint_by_channel(self, channel_name):
        """Match an AMI channel (e.g. PJSIP/101-0000af) to an endpoint.

        Strips the Asterisk channel instance suffix and searches by the
        configured dial string.
        """
        if not channel_name:
            return self.browse()
        if '-' in channel_name:
            channel_name = '-'.join(channel_name.split('-')[:-1])
        return self.sudo().search(
            [('asterisk_channel', '=', channel_name)], limit=1)

    def _get_originate_variables(self):
        """Channel variables for the AMI Originate action of this endpoint."""
        self.ensure_one()
        variables = []
        exten = self.connect_user_id.exten_number or self.exten_number
        if exten:
            variables.extend([
                '__REALCALLERIDNUM={}'.format(exten),
                '__CALLERIDNUMINTERNAL={}'.format(exten),
            ])
        if self.connect_user_id:
            variables.extend(
                self.connect_user_id._get_asterisk_originate_vars())
        header = self.asterisk_auto_answer_header
        if header:
            pos = header.find(':')
            param = header[:pos].strip()
            value = header[pos + 1:].strip()
            if 'PJSIP' in (self.asterisk_channel or '').upper():
                variables.append(
                    'PJSIP_HEADER(add,{})={}'.format(param, value))
            else:
                variables.append('SIPADDHEADER={}: {}'.format(param, value))
        return variables
