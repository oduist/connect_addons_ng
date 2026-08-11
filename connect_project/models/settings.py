from odoo import models
from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_project')


class ConnectProjectSettings(models.Model):
    _inherit = 'connect.settings'
