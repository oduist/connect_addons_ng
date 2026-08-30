from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        result = super()._pre_dispatch(rule, args)
        httprequest = request.httprequest
        if (httprequest.method == 'POST' and
                httprequest.path.startswith('/telnyx/webhook/')):
            httprequest.environ['connect_telnyx.raw_body'] = (
                httprequest.get_data(cache=True)
            )
        return result
