# -*- coding: utf-8 -*-
from odoo import fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    # 'WhatsApp' is added by the connect core; RCS is Telnyx-specific.
    message_type = fields.Selection(
        selection_add=[('RCS', 'RCS')],
        ondelete={'RCS': lambda recs: recs.write({'message_type': 'comment'})},
    )


class MailNotification(models.Model):
    _inherit = 'mail.notification'

    notification_type = fields.Selection(selection_add=[
        ('RCS', 'RCS')
    ], ondelete={'RCS': 'cascade'})
