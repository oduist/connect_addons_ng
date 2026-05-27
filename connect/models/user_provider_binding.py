from odoo import fields, models, release

if release.version_info[0] >= 19:
    from odoo.models import Constraint


class ConnectUserProviderBinding(models.Model):
    _name = 'connect.user.provider.binding'
    _description = 'Connect User ↔ Provider Binding'
    _order = 'user_id, provider_id'

    user_id = fields.Many2one(
        'connect.user', required=True, ondelete='cascade', index=True,
    )
    provider_id = fields.Many2one(
        'connect.provider', required=True, ondelete='cascade', index=True,
    )
    config = fields.Json(
        help='Per-(user, provider) free-form configuration bag. '
             'Reserved for ADR-023 Phase 6 (per-provider settings).',
    )

    if release.version_info[0] >= 19:
        _user_provider_uniq = Constraint(
            'UNIQUE(user_id, provider_id)',
            'A user can only have one binding per provider.',
        )
    else:
        _sql_constraints = [
            ('user_provider_uniq', 'UNIQUE(user_id, provider_id)',
             'A user can only have one binding per provider.'),
        ]
