from odoo import models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_sale')


class ConnectSaleSettings(models.Model):
    _inherit = 'connect.settings'
