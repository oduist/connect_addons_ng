import re
from odoo import fields, models, api
from odoo.exceptions import ValidationError


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


class ConnectEndpoint(models.Model):
    _inherit = 'connect.endpoint'

    auth_user = fields.Char(string='Auth User')
    auth_password = fields.Char(string='Auth Password')
    originate_ring = fields.Boolean(string='Originate Ring', default=True,
        help='Include this endpoint when originating click-to-call calls.')
    auto_answer_header = fields.Selection(
        selection=AUTO_ANSWER_HEADERS,
        string='Auto-Answer Header',
        help='SIP header sent to auto-answer the phone during click-to-call originate.')

    def generate_dialplan(self, params, exten=None):
        """Generate FreeSWITCH dialplan to bridge to this standalone endpoint."""
        self.ensure_one()
        number = exten.number if exten else self.exten_number or self.auth_user
        if not number:
            return ''
        fs_domain = self.env['connect.settings'].sudo().get_param('freeswitch_domain') or '${domain}'

        return self.env['connect.freeswitch.template'].render('dialplan_user_bridge', {
            'number': re.escape(number),
            'user_id': self.connect_user_id.id if self.connect_user_id else 0,
            'exten_id': exten.id if exten else None,
            'record_calls': False,
            'recording_url': '',
            'fs_domain': fs_domain,
        })

    @api.constrains('auth_user')
    def _check_auth_user(self):
        for record in self:
            if record.auth_user and not re.match(r'^[a-zA-Z0-9_.-]+$', record.auth_user):
                raise ValidationError(
                    "Auth user '{}' contains invalid characters. "
                    "Only letters, digits, hyphens, underscores and dots "
                    "are allowed.".format(record.auth_user))
