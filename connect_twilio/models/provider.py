from odoo import models


class TwilioProvider(models.Model):
    _inherit = 'connect.provider'

    def _originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        if self.code != 'twilio':
            return super()._originate_call(
                number=number, res_model=res_model, res_id=res_id, user=user, **kwargs
            )
        return self.env['connect.provider.twilio.config'].sudo()._originate_call(
            number=number, res_model=res_model, res_id=res_id, user=user, **kwargs
        )
