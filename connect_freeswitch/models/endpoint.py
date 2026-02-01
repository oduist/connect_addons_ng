from odoo import fields, models


class ConnectEndpoint(models.Model):
    _inherit = 'connect.endpoint'

    domain = fields.Char('SIP Domain')
    auth_user = fields.Char(string='Auth User')
    auth_password = fields.Char(string='Auth Password')
    sip_enabled = fields.Boolean(string='SIP Enabled', default=False)
    webrtc_enabled = fields.Boolean(string='WebRTC Enabled', default=False)
