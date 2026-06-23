from odoo import fields, models

from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_crm')


class CrmSettings(models.Model):
    _inherit = 'connect.settings'

    auto_create_leads_for_in_calls = fields.Boolean()
    auto_create_leads_for_in_answered_calls = fields.Boolean(
        help='Auto create leads for incoming answered calls.',
        default=True,
    )
    auto_create_leads_for_in_missed_calls = fields.Boolean(
        help='Auto create leads for incoming missed calls.',
        default=True,
    )
    auto_create_leads_for_in_unknown_callers = fields.Boolean(
        help='Auto create leads for callers that do not exist in Contacts.',
        string='For Unknown Callers',
        default=False,
    )
    auto_create_leads_for_out_calls = fields.Boolean()
    auto_create_leads_for_out_answered_calls = fields.Boolean(
        help='Auto create leads for outgoing answered calls.',
        default=True,
    )
    auto_create_leads_for_out_missed_calls = fields.Boolean(
        help='Auto create leads for outgoing not connected calls.',
        default=True,
    )
    auto_create_leads_sales_person = fields.Many2one(
        'res.users',
        domain=[('share', '=', False)],
        string='Default Salesperson',
    )
    auto_create_leads_type = fields.Selection(
        string='Leads type',
        default='lead',
        required=True,
        selection=[('lead', 'Lead'), ('opportunity', 'Opportunity')],
    )
