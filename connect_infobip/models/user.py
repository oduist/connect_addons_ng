# -*- coding: utf-8 -*-
import jinja2
import logging
import re

from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

IDENTITY_RE = re.compile(r'^[A-Za-z0-9\-_]{3,64}$')


class User(models.Model):
    """Infobip presence of a PBX user.

    Every field/method contributed here carries the infobip_ prefix so the
    module co-installs with the other providers, which own their own names
    on this shared ledger model (ADR-031/ADR-035).

    Infobip has no per-user SIP accounts: the agent endpoints are a WebRTC
    identity (web phone) and/or an external phone number. Identities exist
    at Infobip implicitly — minting a token for one registers it.
    """
    _inherit = 'connect.user'

    originate_provider = fields.Selection(
        selection_add=[('infobip', 'Infobip')],
        ondelete={'infobip': 'set null'},
    )
    infobip_exten = fields.Many2one(
        'connect.infobip.exten', ondelete='set null', readonly=True,
        string='Infobip Extension')
    infobip_exten_number = fields.Char(
        related='infobip_exten.number', store=True,
        string='Infobip Extension Number')
    infobip_outgoing_callerid = fields.Many2one(
        'connect.infobip.outgoing_callerid', ondelete='set null',
        string='Infobip Outgoing CallerID')
    infobip_whatsapp_sender_id = fields.Many2one(
        'connect.infobip.whatsapp_sender',
        string='Infobip WhatsApp Sender',
        ondelete='set null',
    )
    infobip_identity = fields.Char('Infobip Identity', copy=False)
    # Enabled out of the box only when Infobip is the sole telephony
    # module; in multi-provider databases the admin enables the Infobip
    # web phone explicitly per user.
    infobip_webrtc_enabled = fields.Boolean(
        'Infobip Web Phone Enabled',
        default=lambda self: self._infobip_is_only_provider())
    infobip_client_priority = fields.Selection(
        [('1', '1'), ('2', '2')], required=True, default='1',
        string='Infobip web client priority',
    )
    infobip_client_ring_timeout = fields.Integer(
        required=True, default=10, string='Infobip web client ring timeout'
    )
    infobip_phone_number = fields.Char(
        'Infobip External Phone',
        help='E.164 number of the external phone rung on inbound calls.')
    infobip_phone_enabled = fields.Boolean('Infobip External Phone Enabled')
    infobip_phone_priority = fields.Selection(
        [('1', '1'), ('2', '2')], required=True, default='2',
        string='Infobip external phone priority',
    )
    infobip_phone_ring_timeout = fields.Integer(
        required=True, default=30, string='Infobip external phone ring timeout'
    )

    if release.version_info[0] >= 19:
        _infobip_identity_uniq = Constraint(
            'UNIQUE(infobip_identity)',
            'This Infobip identity is already used!')
    else:
        _sql_constraints = [
            ('infobip_identity_uniq', 'UNIQUE(infobip_identity)',
             'This Infobip identity is already used!')
        ]

    @api.model
    def _infobip_is_only_provider(self):
        """True when connect_infobip is the only telephony module installed."""
        other = self.env['ir.module.module'].sudo().search_count([
            ('name', 'in', ['connect_twilio', 'connect_freeswitch',
                            'connect_asterisk', 'connect_telnyx']),
            ('state', '=', 'installed'),
        ])
        return not other

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['infobip_exten_number']

    @api.constrains('infobip_identity')
    def _check_infobip_identity(self):
        for rec in self:
            if rec.infobip_identity and not IDENTITY_RE.match(rec.infobip_identity):
                raise ValidationError(
                    'Infobip identity must be 3-64 characters of letters, '
                    'digits, dash or underscore!')

    @api.constrains('infobip_phone_enabled', 'infobip_phone_number')
    def _check_infobip_phone(self):
        for rec in self:
            if rec.infobip_phone_enabled and (
                    not rec.infobip_phone_number
                    or not re.match(r'^\+[0-9]+$', rec.infobip_phone_number)):
                raise ValidationError(
                    'Set the external phone number in E.164 form (+ followed '
                    'by digits) for user {}!'.format(rec.name))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._ensure_infobip_identity()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if vals.get('infobip_webrtc_enabled'):
            self._ensure_infobip_identity()
        return res

    def _ensure_infobip_identity(self):
        for rec in self:
            if rec.infobip_webrtc_enabled and not rec.infobip_identity:
                rec.infobip_identity = rec._default_infobip_identity()

    def _default_infobip_identity(self):
        self.ensure_one()
        login = self.user.login if self.user else ''
        identity = re.sub(r'[^A-Za-z0-9\-_]', '-', login or '').strip('-')
        if len(identity) < 3:
            identity = 'user-{}'.format(self.id)
        if self.search_count([('infobip_identity', '=', identity),
                              ('id', '!=', self.id)]):
            identity = '{}-{}'.format(identity, self.id)
        return identity

    def create_infobip_extension(self):
        self.ensure_one()
        return self.env['connect.infobip.exten'].create_extension(
            self, 'connect.user', current_exten=self.infobip_exten)

    def infobip_render_voicemail_prompt(self):
        # Recorded voicemail is deferred (ADR-035): the rendered prompt is
        # spoken by the ring-exhausted say+hangup fallback.
        self.ensure_one()
        environment = jinja2.Environment()
        template = environment.from_string(self.voicemail_prompt)
        return template.render({'user': self})

    @api.model
    def get_user_by_uri(self, userinfo):
        # Chain after the other providers' lookups (super()), then match
        # the client:{identity}@infobip form our channel adapter renders
        # for WEBRTC legs.
        user = super().get_user_by_uri(userinfo)
        if user:
            return user
        found = re.match(r'^(?:sip|client):([^@]+)@infobip$', userinfo or '')
        if found:
            return self.get_user_by_infobip_identity(found.group(1))
        return user

    @api.model
    def get_user_by_infobip_identity(self, identity):
        if not identity:
            return self.env['connect.user']
        user = self.search([('infobip_identity', '=', identity)], limit=1)
        if user:
            debug(self, 'Found user {} by Infobip identity {}.'.format(
                user.name, identity))
        return user

    @api.model
    def get_infobip_client_token(self):
        """Web phone bootstrap: mint a WebRTC token for the current user.

        Returns the dict consumed by static/src/js/main.js; {'token': False}
        disables the widget, {'error': ...} surfaces a startup problem.
        """
        try:
            has_user_group = self.env.user.has_group('connect.group_user')
            has_admin_group = self.env.user.has_group('connect.group_admin')
            if not (has_user_group or has_admin_group):
                return {'token': False}
            user = self.search([('user', '=', self.env.user.id)])
            if not user:
                logger.info('User %s not found!', self.env.user.id)
                return {'token': False}
            if not user.infobip_webrtc_enabled:
                logger.info(
                    'Infobip web phone for user %s not enabled!',
                    self.env.user.id)
                return {'token': False}
            if not user.infobip_identity:
                user.sudo()._ensure_infobip_identity()
            settings = self.env['connect.settings']
            payload = {
                'identity': user.infobip_identity,
                'displayName': user.name,
                'timeToLive': 28800,
            }
            application_id = settings.sudo().get_param(
                'infobip_webrtc_application_id')
            if application_id:
                payload['applicationId'] = application_id
            resp = settings.infobip_api_request(
                'POST', '/webrtc/1/token', payload)
            return {
                'token': resp.get('token'),
                'identity': user.infobip_identity,
                # callApplication() dials through the Calls configuration so
                # Odoo keeps control of the routing (ADR-035).
                'calls_config_id': settings.sudo().get_param(
                    'infobip_calls_configuration_id'),
                'via_rest': bool(settings.sudo().get_param(
                    'infobip_webphone_via_rest')),
                'expiration': resp.get('expirationTime'),
            }
        except Exception as e:
            logger.exception('Error getting Infobip WebRTC token:')
            return {'error': str(e)}

    @api.constrains('infobip_webrtc_enabled', 'infobip_client_priority',
                    'infobip_client_ring_timeout')
    def _manage_infobip_client_callflow(self):
        for rec in self:
            rec._manage_infobip_channel_callflow(
                'client', rec.infobip_webrtc_enabled)

    @api.constrains('infobip_phone_enabled', 'infobip_phone_priority',
                    'infobip_phone_ring_timeout')
    def _manage_infobip_phone_callflow(self):
        for rec in self:
            rec._manage_infobip_channel_callflow(
                'phone', rec.infobip_phone_enabled)

    def _manage_infobip_channel_callflow(self, channel, enable):
        self.ensure_one()
        Flow = self.env['connect.infobip.user_callflow']
        flow = Flow.search([
            ('user', '=', self.id),
            ('callflow_type', '=', channel),
        ])
        if enable:
            if channel == 'client':
                prio = self.infobip_client_priority
                timeout = self.infobip_client_ring_timeout
            else:
                prio = self.infobip_phone_priority
                timeout = self.infobip_phone_ring_timeout
            vals = {'prio': int(prio), 'ring_timeout': timeout}
            if not flow:
                vals.update({'user': self.id, 'callflow_type': channel})
                Flow.create(vals)
            else:
                flow.write(vals)
        else:
            flow.unlink()
