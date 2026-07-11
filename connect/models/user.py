import logging
from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from .settings import debug

logger = logging.getLogger(__name__)


class User(models.Model):
    _name = 'connect.user'
    _rec_name = 'name'
    _description = 'Connect User'
    _order = 'name'

    name = fields.Char(compute='_get_name', store=True)
    user = fields.Many2one('res.users', string='Odoo User', required=True, domain=[('share', '=', False)])
    record_calls = fields.Boolean(default=True)
    voicemail_enabled = fields.Boolean()
    voicemail_prompt = fields.Text(
        default="Hello, this is {{user.name}}. I'm unable to take your call right now. Please leave a message after the tone.")
    missed_calls_notify = fields.Boolean(default=False, help='Notify user on missed calls.')
    greeting_message = fields.Char()
    summary_prompt = fields.Char()
    active = fields.Boolean(default=True)
    # Provider modules add their key via selection_add (e.g. 'twilio',
    # 'freeswitch', 'asterisk'). When several providers are installed the
    # user picks which one handles click-to-call; with a single provider
    # the dispatcher falls back to it automatically.
    originate_provider = fields.Selection(
        selection=[], string='Click-to-call Provider',
        help='Telephony module used to originate calls for this user. '
             'Leave empty when only one telephony module is installed.')
    # Messaging counterpart of originate_provider: provider modules that
    # implement connect.message.send() add their key via selection_add
    # (e.g. 'twilio', 'bird').
    message_provider = fields.Selection(
        selection=[], string='Messaging Provider',
        help='Messaging module used to send SMS/WhatsApp for this user. '
             'Leave empty when only one messaging module is installed.')

    if release.version_info[0] >= 19:
        _user_uniq = Constraint('UNIQUE("user")', 'This Odoo user account is already defined!')
    else:
        _sql_constraints = [
            ('user_uniq', 'UNIQUE("user")', 'This Odoo user account is already defined!'),
        ]

    @api.depends('user', 'user.name')
    def _get_name(self):
        for rec in self:
            rec.name = rec.user.name if rec.user else ''

    @api.model
    def _pbx_number_fields(self):
        """Names of Char fields on connect.user holding a provider extension
        number. Provider modules append their field (e.g.
        'twilio_exten_number', 'freeswitch_exten_number',
        'asterisk_exten_number')."""
        return []

    def get_pbx_number(self):
        """First non-empty provider extension number of this user."""
        self.ensure_one()
        for field_name in self._pbx_number_fields():
            number = self[field_name]
            if number:
                return number
        return ''

    def manage_group(self, action='add'):
        attribute_name = 'user_ids' if release.version_info[0] >= 19 else 'users'
        # Adjusting res.groups membership is an internal side-effect of
        # connect.user CRUD (already gated by connect.group_admin on the
        # model ACL). Use sudo so a Connect admin who is not also an Odoo
        # system administrator can still create/remove connect.users.
        if self.user and self.user.has_group('base.group_system') and self.user.has_group('base.group_erp_manager'):
            group_connect_admin = self.env.ref('connect.group_admin').sudo()
            if action == 'add':
                group_connect_admin.write({attribute_name: [(4, self.user.id)]})
            else:
                group_connect_admin.with_context(install_mode=True).write({attribute_name: [(3, self.user.id)]})
        elif self.user:
            group_connect_user = self.env.ref('connect.group_user').sudo()
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
        number_fields = self._pbx_number_fields()
        if not number_fields:
            return False
        domain = ['|'] * (len(number_fields) - 1) + [
            [field_name, '=', search_query] for field_name in number_fields]
        search_fields = ['id', 'name', 'user'] + number_fields
        user = self.sudo().search_read(domain, search_fields, limit=1)
        if not user:
            return False
        # Keep the historical key used by the transfer widget.
        user[0]['exten_number'] = next(
            (user[0][f] for f in number_fields if user[0].get(f)), '')
        return user[0]

    @api.model
    def get_user_by_uri(self, userinfo):
        """Lookup connect.user by SIP/client URI. No-op in core; overridden by provider modules."""
        return self.env['connect.user']
