from odoo import models


class FreeSwitchProvider(models.Model):
    _inherit = 'connect.provider'

    def _originate_call(self, number, res_model=None, res_id=None, **kwargs):
        if self.code != 'freeswitch':
            return super()._originate_call(
                number=number, res_model=res_model, res_id=res_id, **kwargs
            )
        # `user` and other Twilio-only kwargs are accepted-and-ignored
        # because the unified façade may pass them through.
        return self.env['connect.call']._freeswitch_originate_call(
            number=number, res_model=res_model, res_id=res_id,
        )
