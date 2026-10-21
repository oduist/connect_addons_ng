# -*- coding: utf-8 -*-
import jinja2
import logging
import random
import re
import string

from voiceml.exceptions import ApiError

from odoo import fields, models, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from .voiceml_response import Dial, VoiceResponse

from odoo.addons.connect.models.settings import debug
from .settings import MAX_EXTEN_LEN, format_connect_response
from .voiceml import pretty_xml

logger = logging.getLogger(__name__)

RE_SIP_URI = re.compile(r'^(?:sips?:)?([^@]+)@([^;>?]+)')


class User(models.Model):
    _inherit = 'connect.user'

    # Not field-level required: with several telephony modules installed a
    # user may have no VoiceTel account at all. Username/domain become
    # mandatory only when the VoiceTel SIP phone is enabled.
    voicetel_username = fields.Char(string='VoiceTel Username')

    if release.version_info[0] >= 19:
        _voicetel_username_uniq = Constraint(
            'UNIQUE(voicetel_username)',
            'This VoiceTel username is already defined!')
    else:
        _sql_constraints = [
            ('voicetel_username_uniq', 'UNIQUE(voicetel_username)',
             'This VoiceTel username is already defined!'),
        ]

    @api.constrains('voicetel_username')
    def _check_voicetel_username(self):
        for rec in self:
            if rec.voicetel_username and not rec.voicetel_username.isalnum():
                raise ValidationError('VoiceTel username must be alphanumeric!')

    @api.constrains('voicetel_sip_enabled', 'voicetel_username', 'voicetel_domain', 'voicetel_domain.domain_name')
    def _check_voicetel_account(self):
        for rec in self:
            if rec.voicetel_sip_enabled and not (
                    rec.voicetel_username and rec.voicetel_domain):
                raise ValidationError(
                    'Username and SIP domain are required to enable the '
                    'VoiceTel phone for user {}!'.format(rec.name))

    @api.model
    def _pbx_number_fields(self):
        return super()._pbx_number_fields() + ['voicetel_exten_number']

    originate_provider = fields.Selection(
        selection_add=[('voicetel', 'VoiceTel')],
        ondelete={'voicetel': 'set null'},
    )
    message_provider = fields.Selection(
        selection_add=[('voicetel', 'VoiceTel')],
        ondelete={'voicetel': 'set null'},
    )
    voicetel_exten = fields.Many2one(
        'connect.voicetel.exten', ondelete='set null', readonly=True,
        string='VoiceTel Extension')
    voicetel_exten_number = fields.Char(
        related='voicetel_exten.number', store=True,
        string='VoiceTel Extension Number')
    voicetel_outgoing_callerid = fields.Many2one(
        'connect.voicetel.outgoing_callerid', ondelete='set null',
        string='VoiceTel Outgoing CallerID')

    def create_voicetel_extension(self):
        self.ensure_one()
        return self.env['connect.voicetel.exten'].create_extension(
            self, 'connect.user', current_exten=self.voicetel_exten)

    def voicetel_caller_id(self):
        """Caller ID to present for calls this user places.

        The extension is the identity a colleague should see. Without one,
        fall back to a real number -- the user's own outgoing caller ID,
        else the default one -- and only then to the SIP identity: an empty
        caller ID makes the platform substitute a number of its own.
        """
        self.ensure_one()
        if self.voicetel_exten.number:
            return self.voicetel_exten.number
        callerid = self.voicetel_outgoing_callerid.number or self.env[
            'connect.voicetel.outgoing_callerid'
        ].sudo().search([('is_default', '=', True)], limit=1).number
        if not callerid and self.voicetel_username and self.voicetel_domain:
            callerid = self.voicetel_username
        logger.warning(
            'Exten not set for user %s, calling as %s',
            self.name, callerid or '(no caller ID)',
        )
        return callerid or ''

    @api.model
    def get_user_by_uri(self, userinfo):
        """Lookup connect.user by its SIP address on a VoiceTel domain.

        Only a URI whose host is one of this module's SIP domains is matched
        here, so a Twilio or FreeSWITCH user with the same username is left
        to its own provider when several modules are installed.
        """
        if isinstance(userinfo, str) and userinfo:
            found = RE_SIP_URI.search(userinfo)
            if found:
                username, host = found.group(1), found.group(2).lower()
                domain = self.env['connect.voicetel.domain'].sudo().search(
                    [('domain_name', '=', host)], limit=1)
                user = self.env['connect.user'].sudo().search([
                    ('voicetel_username', '=', username),
                    ('voicetel_domain', '=', domain.id if domain else 0),
                ], limit=1)
                if user:
                    debug(self, 'Found user: {} by {}.'.format(user.name, userinfo))
                    return user
            elif userinfo.isalnum():
                # A bare username: the registrar reports the From user part
                # on calls placed from a registered device.
                user = self.env['connect.user'].sudo().search(
                    [('voicetel_username', '=', userinfo)], limit=1)
                if user:
                    return user
        return super().get_user_by_uri(userinfo)

    voicetel_sid = fields.Char('VoiceTel Credential SID', readonly=True)
    # Kept readable by its owner: the browser phone registers with the SIP
    # digest password, so unlike the Twilio module it is never masked
    # (ADR-066 decision 5). The core record rules keep a connect.user private
    # to its owner; res.users.get_voicetel_sip_user_config() is the only RPC
    # that hands it to the browser, and only for the calling user.
    voicetel_password = fields.Char(
        string='VoiceTel SIP Password',
        groups="connect.group_admin,connect.group_user",
    )
    voicetel_domain = fields.Many2one(
        'connect.voicetel.domain',
        string='VoiceTel SIP Domain',
        ondelete='cascade',
        default=lambda self: self._default_voicetel_domain(),
    )

    @api.model
    def _default_voicetel_domain(self):
        # During module installation on a database with existing
        # connect.user rows the new column is initialized before the
        # domain table exists -- return no default in that case.
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.tables"
            " WHERE table_name = 'connect_voicetel_domain'")
        if not self.env.cr.fetchone():
            return False
        return self.env['connect.voicetel.domain'].search([], limit=1)

    voicetel_sip_enabled = fields.Boolean('VoiceTel SIP Phone Enabled')
    voicetel_ring_timeout = fields.Integer(
        required=True, default=30, string='VoiceTel ring timeout'
    )
    # The browser phone registers with the same SIP credential as a desk
    # phone; this switch only decides whether the browser loads it.
    voicetel_phone_enabled = fields.Boolean('VoiceTel Browser Phone')
    voicetel_ring_volume = fields.Integer(default=100, string='Ring Volume')
    voicetel_mask_call_number = fields.Boolean(
        string='Mask Numbers',
        help='Mask the middle digits of phone numbers in the web phone.')
    voicetel_call_popup_is_enabled = fields.Boolean(
        string='Call Popup', default=True)
    voicetel_call_popup_is_sticky = fields.Boolean(string='Sticky Popup')
    voicetel_uri = fields.Char('VoiceTel SIP URI', compute='_get_voicetel_sip_uri')
    voicetel_application = fields.Many2one(
        'connect.voicetel.voiceml', string='VoiceML App')

    @api.depends('voicetel_username', 'voicetel_domain.domain_name')
    def _get_voicetel_sip_uri(self):
        for rec in self:
            if rec.voicetel_username and rec.voicetel_domain:
                rec.voicetel_uri = '{}@{}'.format(
                    rec.voicetel_username, rec.voicetel_domain.domain_name)
            else:
                rec.voicetel_uri = ''

    def _voicetel_create_sip_account(self, username, password, client=None):
        self.ensure_one()
        try:
            client = client or self.env['connect.settings'].get_voicetel_client()
            credential = client.sip.credential_lists.credentials(
                self.voicetel_domain.cred_list_sid
            ).create(username=username, password=password)
            if not credential:
                raise ValidationError('Cannot create a SIP user!')
            return credential.sid
        except Exception as e:
            if ('already exists' in str(e) or '409' in str(e)
                    or 'already in use' in str(e) or '21632' in str(e)):
                debug(
                    self,
                    'SIP credential {} already exists in VoiceML - importing '
                    'existing SID'.format(username),
                )
                return self._voicetel_import_existing_sip_credential(
                    username, client
                )
            else:
                raise ValidationError(format_connect_response(e))

    def _voicetel_import_existing_sip_credential(self, username, client=None):
        """Import an existing SIP credential from VoiceML by username."""
        self.ensure_one()
        client = client or self.env['connect.settings'].get_voicetel_client()
        try:
            credentials = client.sip.credential_lists.credentials(
                self.voicetel_domain.cred_list_sid
            ).iter()
            for credential in credentials:
                if credential.username == username:
                    debug(
                        self,
                        'Found existing SIP credential for {} with SID {}'.format(
                            username, credential.sid
                        ),
                    )
                    return credential.sid
            raise ValidationError(
                'SIP credential "{}" already exists but could not be found '
                'in the credential list'.format(username)
            )
        except ValidationError:
            raise
        except Exception as e:
            debug(
                self,
                'Error importing existing SIP credential for {}: {}'.format(
                    username, str(e)
                ),
                level='error',
            )
            raise ValidationError(
                'Failed to import existing SIP credential for "{}": {}'.format(
                    username, format_connect_response(e)
                )
            )

    def _voicetel_update_sip_password(self, password):
        self.ensure_one()
        if not self.voicetel_sid:
            logger.warning(
                'SIP account %s SID not set, not updating.', self.id
            )
            return
        try:
            client = self.env['connect.settings'].get_voicetel_client()
            client.sip.credential_lists.credentials(
                self.voicetel_domain.cred_list_sid
            ).update(self.voicetel_sid, password=password)
        except Exception as e:
            if 'not found' in str(e):
                debug(
                    self,
                    'SIP cred {} SID {} not found in VoiceML'.format(
                        self.voicetel_username, self.voicetel_sid
                    ),
                )
                self.voicetel_sid = self._voicetel_create_sip_account(
                    self.voicetel_username, password)
            else:
                raise ValidationError(format_connect_response(e))

    def voicetel_delete_sip_account(self):
        self.ensure_one()
        if not self.voicetel_sid:
            logger.warning(
                'Attempt to delete SIP account %s (%s) without SID!',
                self.id,
                self.name,
            )
            return
        try:
            client = self.env['connect.settings'].get_voicetel_client()
            client.sip.credential_lists.credentials(
                self.voicetel_domain.cred_list_sid
            ).delete(self.voicetel_sid)
            debug(
                self,
                'Deleted SIP account {}.'.format(self.voicetel_username),
            )
            return True
        except Exception as e:
            if 'not found' in str(e):
                logger.warning(
                    'SIP account %s was not present in VoiceML.',
                    self.voicetel_username,
                )
            else:
                raise ValidationError(format_connect_response(e))

    @staticmethod
    def generate_voicetel_password():
        """Generate a strong password for a SIP credential."""
        password_chars = [
            random.choice(string.ascii_lowercase),
            random.choice(string.ascii_uppercase),
            random.choice(string.digits),
        ]
        all_chars = string.ascii_letters + string.digits
        password_chars += random.choices(
            all_chars, k=16 - len(password_chars)
        )
        random.shuffle(password_chars)
        return ''.join(password_chars)

    @api.model
    def _voicetel_sync_enabled(self):
        return bool(self.env['connect.settings'].sudo().get_param(
            'voicetel_auto_sync'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('voicetel_sip_enabled') and not vals.get('voicetel_password'):
                vals['voicetel_password'] = self.generate_voicetel_password()
        recs = super().create(vals_list)
        if self.env.context.get('no_voicetel_create'):
            return recs
        for rec in recs:
            if rec.voicetel_sip_enabled and rec.voicetel_password and \
                    self._voicetel_sync_enabled():
                rec.with_context(skip_voicetel_sync=True).voicetel_sid = (
                    rec._voicetel_create_sip_account(
                        username=rec.voicetel_username,
                        password=rec.voicetel_password,
                    )
                )
        return recs

    def write(self, vals):
        if self.env.context.get('skip_voicetel_sync'):
            return super().write(vals)
        if 'voicetel_username' in vals and any(
                rec.voicetel_sid and rec.voicetel_username
                and rec.voicetel_username != vals['voicetel_username']
                for rec in self):
            raise ValidationError(
                'The VoiceTel username cannot be changed while its SIP '
                'credential exists. Disable the SIP phone first!')
        res = super().write(vals)
        if not self._voicetel_sync_enabled():
            return res
        touches_credential = (
            'voicetel_password' in vals or 'voicetel_sip_enabled' in vals)
        if not touches_credential:
            return res
        for rec in self:
            if not rec.voicetel_sip_enabled:
                if 'voicetel_sip_enabled' in vals and rec.voicetel_sid:
                    rec.voicetel_delete_sip_account()
                    rec.with_context(skip_voicetel_sync=True).voicetel_sid = False
                continue
            if not rec.voicetel_password:
                rec.with_context(skip_voicetel_sync=True).voicetel_password = (
                    self.generate_voicetel_password())
            if rec.voicetel_sid:
                if 'voicetel_password' in vals:
                    rec._voicetel_update_sip_password(rec.voicetel_password)
            else:
                rec.with_context(skip_voicetel_sync=True).voicetel_sid = (
                    rec._voicetel_create_sip_account(
                        rec.voicetel_username, rec.voicetel_password))
        return res

    def unlink(self):
        for rec in self:
            if rec.voicetel_sid and self._voicetel_sync_enabled():
                rec.voicetel_delete_sip_account()
        return super(User, self).unlink()

    def voicetel_render_sip(self, response, request, params):
        callerId = self._voicetel_get_caller_id(request, params)
        settings = self.env['connect.settings'].sudo()
        record_status_url = settings.voicetel_webhook_url(
            'voicetel/webhook/recordingstatus')
        status_url = settings.voicetel_webhook_url('voicetel/webhook/callstatus')
        dial_sip_kwargs = {
            'timeout': self.voicetel_ring_timeout,
            'callerId': callerId,
            'action': (
                params.get('dial_action_url') or self._voicetel_get_dial_action_url()
            ),
        }
        if self.record_calls:
            dial_sip_kwargs.update(
                {
                    'recordingStatusCallback': record_status_url,
                    'record': 'record-from-answer-dual',
                }
            )
        dial_sip = Dial(**dial_sip_kwargs)
        dial_sip.sip(
            'sip:{}'.format(self.voicetel_uri),
            statusCallbackEvent='initiated answered completed',
            statusCallback=status_url,
        )
        response.append(dial_sip)

    def voicetel_render_voicemail_prompt(self):
        self.ensure_one()
        environment = jinja2.Environment()
        template = environment.from_string(self.voicemail_prompt)
        return template.render({'user': self})

    def voicetel_get_greeting_message(self, response):
        self.ensure_one()
        response.say(
            self.greeting_message,
            language=self.language or 'en-US',
            voice=self.voice or 'Woman',
        )

    def voicetel_get_voicemail_prompt(self, response):
        self.ensure_one()
        voicemail_prompt = self.voicetel_render_voicemail_prompt()
        response.say(
            voicemail_prompt,
            language=self.language or 'en-US',
            voice=self.voice or 'Woman',
        )

    def voicetel_render_voicemail(self, response, request, params):
        voicemail_record_status_url = self.env[
            'connect.settings'].sudo().voicetel_webhook_url(
                'voicetel/webhook/vm_recordingstatus')
        self.voicetel_get_voicemail_prompt(response)
        response.record(
            maxLength=120,
            finishOnKey='#',
            playBeep=True,
            recordingStatusCallback=voicemail_record_status_url,
        )

    def voicetel_render(self, request=None, params=None):
        self.ensure_one()
        request = dict(request or {})
        params = dict(params or {})
        channel = self.env['connect.channel'].search(
            [('sid', '=', request.get('CallSid'))], order='id desc'
        )
        call = channel.call
        response = VoiceResponse()
        if call:
            done_callflow_ids = (
                self.env['connect.voicetel.user_callflow_call']
                .sudo()
                .search([('call', '=', call.id)])
                .mapped('callflow')
                .mapped('id')
            )
            if not done_callflow_ids and self.greeting_message:
                self.voicetel_get_greeting_message(response)
            next_call_flow = (
                self.env['connect.voicetel.user_callflow']
                .sudo()
                .search(
                    [
                        ('user', '=', self.id),
                        ('id', 'not in', done_callflow_ids),
                    ],
                    order='prio',
                    limit=1,
                )
            )
            if next_call_flow:
                self.env['connect.voicetel.user_callflow_call'].sudo().create(
                    {
                        'call': call.id,
                        'callflow': next_call_flow.id,
                    }
                )
                getattr(self, next_call_flow.method)(
                    response, request, params
                )
                debug(self, pretty_xml(response.to_xml()))
                return response.to_xml()
            else:
                callflows = (
                    self.env['connect.voicetel.user_callflow_call']
                    .sudo()
                    .search([('call', '=', call.id)])
                )
                callflows.sudo().unlink()
                response.hangup()
                return response.to_xml()
        else:
            # No ledger call to walk against: the click-to-call originate path
            # builds the dialplan before the channel exists. Only the first
            # callflow can ever run from here -- every verb after a <Dial>
            # with an action URL is unreachable -- so render just that one
            # and carry the callflows already dialed in the action URL.
            done_ids = self._voicetel_parse_done_callflows(request)
            next_flow = (
                self.env['connect.voicetel.user_callflow']
                .sudo()
                .search(
                    [('user', '=', self.id), ('id', 'not in', done_ids)],
                    order='prio',
                    limit=1,
                )
            )
            if not next_flow:
                response.hangup()
                return response.to_xml()
            params['dial_action_url'] = self._voicetel_get_dial_action_url(
                done_ids + [next_flow.id]
            )
            getattr(self, next_flow.method)(response, request, params)
            debug(self, pretty_xml(response.to_xml()))
            return response.to_xml()

    def _voicetel_get_dial_action_url(self, done_callflows=None):
        """URL VoiceML requests when a <Dial> of this user's callflow ends.

        ``done_callflows`` carries the ids already dialed, so the walk can
        resume correctly even before the ledger call exists.
        """
        self.ensure_one()
        path = 'voicetel/webhook/connect.user/call_action/{}'.format(self.id)
        if done_callflows:
            path += '?done_callflows={}'.format(
                ','.join(str(flow_id) for flow_id in done_callflows)
            )
        return self.env['connect.settings'].sudo().voicetel_webhook_url(path)

    @api.model
    def _voicetel_parse_done_callflows(self, request):
        """Callflow ids the action URL reports as already dialed."""
        raw = str((request or {}).get('done_callflows') or '')
        return [
            int(chunk) for chunk in raw.split(',')
            if chunk.strip().isdigit()
        ]

    def _voicetel_get_caller_id(self, request, params):
        caller_user = self.env['connect.user'].get_user_by_uri(
            request.get('Caller')
        )
        if caller_user:
            callerId = caller_user.voicetel_caller_id()
        else:
            callerId = request.get('Caller')
        return callerId

    def _voicetel_get_caller_name(self, request, params):
        caller_user = self.env['connect.user'].get_user_by_uri(
            request.get('Caller')
        )
        caller_name = params.get('CallerName', False)
        if caller_user:
            caller_name = caller_user.name
        return caller_name

    @api.constrains('voicetel_sip_enabled')
    def _voicetel_manage_sip_callflow(self):
        for rec in self:
            rec._voicetel_manage_channel_callflow('sip', rec.voicetel_sip_enabled)

    @api.constrains('voicemail_enabled')
    def _voicetel_manage_voicemail_enabled(self):
        for rec in self:
            rec._voicetel_manage_channel_callflow(
                'voicemail', rec.voicemail_enabled, prio=10)

    def _voicetel_manage_channel_callflow(self, channel, enable, prio=1):
        self.ensure_one()
        Callflow = self.env['connect.voicetel.user_callflow'].sudo()
        existing = Callflow.search([
            ('user', '=', self.id),
            ('callflow_type', '=', channel),
        ])
        if enable:
            if not existing:
                Callflow.create({
                    'user': self.id,
                    'callflow_type': channel,
                    'prio': prio,
                    'method': 'voicetel_render_{}'.format(channel),
                })
        else:
            existing.unlink()

    @api.onchange('voicetel_domain')
    def _restrict_voicetel_domain_change(self):
        if self.voicetel_sip_enabled and self.voicetel_sid:
            raise ValidationError(
                'You cannot change the SIP domain of an existing SIP account! '
                'Disable the SIP phone first!'
            )

    @api.model
    def voicetel_on_call_action(self, record_id, request):
        user = self.browse(record_id)
        user._voicetel_record_done_callflows(request)
        if user._voicetel_is_call_action_final(request):
            user._voicetel_clear_done_callflows(request)
            response = VoiceResponse()
            response.hangup()
            return response.to_xml()
        return user.voicetel_render(request)

    def _voicetel_clear_done_callflows(self, request):
        """Drop the walk bookkeeping once the call stops progressing."""
        self.ensure_one()
        channel = self.env['connect.channel'].sudo().search(
            [('sid', '=', request.get('CallSid'))], order='id desc'
        )
        call = channel.call
        if not call:
            return
        self.env['connect.voicetel.user_callflow_call'].sudo().search(
            [('call', '=', call.id)]
        ).unlink()

    def _voicetel_record_done_callflows(self, request):
        """Log the callflows the originate path already dialed.

        connect.settings.originate_call renders the dialplan before the
        channel exists, so voicetel_render() cannot log the callflows it used
        there. The action URL carries the ids instead; folding them into the
        ledger here keeps the stateful walk from ringing the same device
        twice.
        """
        self.ensure_one()
        callflow_ids = self._voicetel_parse_done_callflows(request)
        if not callflow_ids:
            return
        channel = self.env['connect.channel'].sudo().search(
            [('sid', '=', request.get('CallSid'))], order='id desc'
        )
        call = channel.call
        if not call:
            return
        done = self.env['connect.voicetel.user_callflow_call'].sudo()
        already = done.search([('call', '=', call.id)]).mapped('callflow').ids
        missing = self.env['connect.voicetel.user_callflow'].sudo().browse(
            [i for i in callflow_ids if i not in already]
        ).exists()
        if missing:
            done.create([
                {'call': call.id, 'callflow': flow.id} for flow in missing
            ])

    def _voicetel_is_call_action_final(self, request):
        """Whether the callflow walk must stop at this <Dial> action callback.

        The parent leg is reported in CallStatus -- still 'in-progress' while
        the caller is on the line -- and the outcome of the dialed leg in
        DialCallStatus. Only a leg that was never picked up may move on to
        the next device: one that was answered and then hung up has to end
        the call instead of ringing the rest of the callflow.
        """
        parent_status = request.get('CallStatus')
        if parent_status in ('completed', 'canceled', 'busy', 'failed',
                             'no-answer'):
            return True
        dial_status = request.get('DialCallStatus')
        if dial_status:
            return dial_status not in ('busy', 'no-answer', 'failed')
        return False
