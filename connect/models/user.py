import logging
from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
from odoo.models import Constraint
from .settings import debug

logger = logging.getLogger(__name__)


class User(models.Model):
    _name = 'connect.user'
    _rec_name = 'name'
    _description = 'Connect User'
    _order = 'name'

    callflow = fields.One2many('connect.user_callflow', 'user')
    endpoint_ids = fields.One2many('connect.endpoint', 'connect_user_id', string='Endpoints')
    endpoint_count = fields.Integer(compute='_compute_endpoint_count')
    exten = fields.Many2one('connect.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    name = fields.Char(compute='_get_name', store=True)
    user = fields.Many2one('res.users', string='Odoo User', required=True, domain=[('share', '=', False)])
    record_calls = fields.Boolean(default=True)
    voicemail_enabled = fields.Boolean()
    voicemail_prompt = fields.Text(
        default="Hello, this is {{user.name}}. I'm unable to take your call right now. Please leave a message after the tone.")
    # Core defines the field with no domain — `status` is a Twilio-only
    # concept (caller-ID validation) and referencing it from core breaks
    # name_search whenever connect_twilio is not installed. connect_twilio
    # re-declares the field with the validation-aware domain.
    outgoing_callerid = fields.Many2one('connect.outgoing_callerid', ondelete='set null')
    missed_calls_notify = fields.Boolean(default=False, help='Notify user on missed calls.')
    greeting_message = fields.Char()
    summary_prompt = fields.Char()
    active = fields.Boolean(default=True)
    provider_binding_ids = fields.One2many(
        'connect.user.provider.binding', 'user_id',
        string='Provider Bindings',
    )
    provider_ids = fields.Many2many(
        'connect.provider',
        compute='_compute_provider_ids', store=True, readonly=True,
        string='Providers',
        help='Telephony providers this user is reachable on '
             '(computed from provider_binding_ids).',
    )

    _user_uniq = Constraint('UNIQUE("user")', 'This Odoo user account is already defined!')

    def _compute_endpoint_count(self):
        for rec in self:
            rec.endpoint_count = len(rec.endpoint_ids)

    @api.depends('provider_binding_ids.provider_id')
    def _compute_provider_ids(self):
        for rec in self:
            rec.provider_ids = rec.provider_binding_ids.mapped('provider_id')

    @api.depends('user', 'user.name')
    def _get_name(self):
        for rec in self:
            rec.name = rec.user.name if rec.user else ''

    def manage_group(self, action='add'):
        attribute_name = 'user_ids' if release.version_info[0] >= 19 else 'users'
        if self.user and self.user.has_group('base.group_system') and self.user.has_group('base.group_erp_manager'):
            group_connect_admin = self.env.ref('connect.group_admin')
            if action == 'add':
                group_connect_admin.write({attribute_name: [(4, self.user.id)]})
            else:
                group_connect_admin.with_context(install_mode=True).write({attribute_name: [(3, self.user.id)]})
        elif self.user:
            group_connect_user = self.env.ref('connect.group_user')
            if action == 'add':
                group_connect_user.write({attribute_name: [(4, self.user.id)]})
            else:
                group_connect_user.with_context(install_mode=True).write({attribute_name: [(3, self.user.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for connect_user in recs:
            connect_user.manage_group()
        if recs and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return recs

    def unlink(self):
        for rec in self:
            rec.manage_group('remove')
        res = super(User, self).unlink()
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    def write(self, vals):
        if 'user' in vals.keys():
            self.manage_group('remove')
        res = super().write(vals)
        self.manage_group()
        if res and not self.env.context.get('no_clear_cache'):
            if release.version_info[0] >= 17:
                self.env.registry.clear_cache()
            else:
                self.clear_caches()
        return res

    @api.model
    def get_user_by_exten_number(self, search_query):
        has_group = self.env.user.has_group
        if not any([has_group('connect.group_user'), has_group('connect.group_admin')]):
            raise ValidationError('Only Connect users can search other Connect users!')
        domain = [['exten_number', '=', search_query]]
        search_fields = ['id', 'name', 'exten_number', 'user']
        user = self.sudo().search_read(domain, search_fields, limit=1, order='exten_number asc')
        return user[0] if user else False

    @api.model
    def get_user_by_uri(self, userinfo):
        """Lookup connect.user by SIP/client URI. No-op in core; overridden by provider modules."""
        return self.env['connect.user']

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.exten'].create_extension(self, 'user')
