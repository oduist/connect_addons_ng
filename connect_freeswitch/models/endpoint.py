import re
from odoo import fields, models, api
from odoo.exceptions import ValidationError


class ConnectEndpoint(models.Model):
    _inherit = 'connect.endpoint'

    auth_user = fields.Char(string='Auth User')
    auth_password = fields.Char(string='Auth Password')
    sip_enabled = fields.Boolean(string='SIP Enabled', default=False)
    sip_ring = fields.Boolean(string='SIP Ring', default=True)
    webrtc_enabled = fields.Boolean(string='WebRTC Enabled', default=False)
    webrtc_ring = fields.Boolean(string='WebRTC Ring', default=True)

    @api.constrains('auth_user')
    def _check_auth_user(self):
        for record in self:
            if record.auth_user and not re.match(r'^[a-zA-Z0-9_.-]+$', record.auth_user):
                raise ValidationError(
                    "Auth user '{}' contains invalid characters. "
                    "Only letters, digits, hyphens, underscores and dots "
                    "are allowed.".format(record.auth_user))
