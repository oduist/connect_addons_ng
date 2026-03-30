from odoo import fields, models


class ConnectEndpoint(models.Model):
    _inherit = 'connect.endpoint'

    auth_user = fields.Char(string='Auth User')
    auth_password = fields.Char(string='Auth Password')
    sip_enabled = fields.Boolean(string='SIP Enabled', default=False)
    sip_ring = fields.Boolean(string='SIP Ring', default=True)
    webrtc_enabled = fields.Boolean(string='WebRTC Enabled', default=False)
    webrtc_ring = fields.Boolean(string='WebRTC Ring', default=True)
