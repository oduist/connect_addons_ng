import logging
from odoo import fields, models, api

logger = logging.getLogger(__name__)


class CallFlow(models.Model):
    _name = 'connect.callflow'
    _description = 'Call Flow'
    _order = 'name asc'

    name = fields.Char(required=True)
    provider_id = fields.Many2one(
        'connect.provider', ondelete='set null', index=True, copy=False,
        help='Telephony provider that renders this callflow.',
    )
    exten = fields.Many2one('connect.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    language = fields.Char(default='en-US', required=True)
    voice = fields.Char(required=True, default='Woman')
    gather_input = fields.Boolean()
    gather_input_type = fields.Selection(string='Input Type',
        selection=[
            ('dtmf speech', 'DTMF + speech'),
            ('dtmf', 'DTMF'),
            ('speech', 'Speech')
        ], required=True, default='dtmf speech')
    gather_timeout = fields.Integer(string='Timeout', default=5)
    gather_hints = fields.Char('Hints', default='This is a phrase I expect to hear, department name or extension number')
    prompt_message = fields.Text('Prompt Message',
        default='Welcome to our company! Please enter the extension number of person '
                'you wish to dial or wait 5 seconds till I start connecting your call')
    invalid_input_message = fields.Text(default='We received wrong input. Please try again!')
    gather_digits = fields.Integer(required=True, default=1)
    choices = fields.One2many('connect.callflow_choice', 'callflow')
    ring_users = fields.Many2many('connect.user')
    record_calls = fields.Boolean()
    voicemail_prompt = fields.Text()
    voicemail_enabled = fields.Boolean()

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.exten'].create_extension(self, 'callflow')
