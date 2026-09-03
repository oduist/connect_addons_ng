from odoo import models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_account')


class ConnectAccountSettings(models.Model):
    _inherit = 'connect.settings'
