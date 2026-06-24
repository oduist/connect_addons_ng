from odoo import fields, models

from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_helpdesk')


class HelpdeskSettings(models.Model):
    _inherit = 'connect.settings'

    auto_create_tickets_for_in_calls = fields.Boolean()
    auto_create_tickets_for_in_answered_calls = fields.Boolean(
        help='Auto create tickets for incoming answered calls.',
        default=True,
    )
    auto_create_tickets_for_in_missed_calls = fields.Boolean(
        help='Auto create tickets for incoming missed calls.',
        default=True,
    )
    auto_create_tickets_for_in_unknown_callers = fields.Boolean(
        help='Auto create tickets for callers that do not exist in Contacts.',
        string='For Unknown Callers',
        default=False,
    )
    auto_create_tickets_for_out_calls = fields.Boolean()
    auto_create_tickets_for_out_answered_calls = fields.Boolean(
        help='Auto create tickets for outgoing answered calls.',
        default=True,
    )
    auto_create_tickets_for_out_missed_calls = fields.Boolean(
        help='Auto create tickets for outgoing not connected calls.',
        default=True,
    )
    auto_create_tickets_team = fields.Many2one(
        'helpdesk.team',
        string='Default Helpdesk Team',
        help='Team used for tickets auto-created from calls.',
    )
    auto_create_tickets_user = fields.Many2one(
        'res.users',
        domain=[('share', '=', False)],
        string='Default Assignee',
        help='Fallback assignee when no PBX user maps to the call.',
    )
