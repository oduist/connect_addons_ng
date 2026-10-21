# -*- coding: utf-8 -*-

import logging
import re

from voiceml.exceptions import ApiError

from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError
from .voiceml_response import Dial, VoiceResponse
from odoo.addons.connect.models.settings import debug
from .settings import (
    format_connect_response, DEFAULT_VOICETEL_SIP_SUFFIX, VOICETEL_WSS_PORT)
from .voiceml import pretty_xml


logger = logging.getLogger(__name__)

# VoiceML answers a SIP domain name already held by another tenant with
# 409 / code 21631; the helper library surfaces both in the exception text.
def _domain_taken(error):
    # VoiceML answers a taken domain name with 409 / code 21631.
    return isinstance(error, ApiError) and (
        error.code == 21631 or error.status_code == 409)


class Domain(models.Model):
    _name = "connect.voicetel.domain"
    _rec_name = "friendly_name"
    _description = "VoiceTel SIP Domain"
    _order = "friendly_name"

    sid = fields.Char("SID", readonly=True)
    application = fields.Many2one(
        "connect.voicetel.voiceml",
        ondelete="restrict",
        required=True,
        default=lambda self: self.get_domain_app(),
    )
    cred_list_sid = fields.Char("Cred List SID", readonly=True)
    subdomain = fields.Char(
        required=True, string='Label',
        help='Tenant label; the SIP domain is <label>.<suffix> where the '
             'suffix comes from the VoiceTel settings.')
    domain_name = fields.Char(compute="_get_domain_name", store=True)
    wss_url = fields.Char(compute="_get_domain_name", store=True, string='WebSocket URL')
    friendly_name = fields.Char(required=True)
    sip_registration = fields.Boolean("SIP Registration", readonly=True, default=True)
    delete_protection = fields.Boolean(default=True)

    if release.version_info[0] >= 19:
        _uniq_subdomain = Constraint(
            'UNIQUE(subdomain)', 'This label is already used!')
    else:
        _sql_constraints = [
            ("uniq_subdomain", "UNIQUE(subdomain)", "This label is already used!")
        ]

    @api.constrains('subdomain')
    def _check_subdomain(self):
        for rec in self:
            if rec.subdomain and not re.match(
                    r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', rec.subdomain):
                raise ValidationError(
                    'The label must be a DNS label: lowercase letters, digits '
                    'and hyphens, e.g. "acme".')

    @api.depends('subdomain')
    def _get_domain_name(self):
        settings = self.env['connect.settings'].sudo()
        suffix = (settings.get_param('voicetel_sip_suffix')
                  or DEFAULT_VOICETEL_SIP_SUFFIX).strip('.')
        for rec in self:
            if rec.subdomain:
                rec.domain_name = '{}.{}'.format(rec.subdomain, suffix)
                rec.wss_url = 'wss://{}:{}'.format(rec.domain_name, VOICETEL_WSS_PORT)
            else:
                rec.domain_name = ''
                rec.wss_url = ''

    def get_domain_app(self):
        app = self.env["connect.voicetel.voiceml"].search(
            [
                ("code_type", "=", "model_method"),
                ("model", "=", "connect.voicetel.domain"),
                ("method", "=", "route_call"),
            ],
            limit=1,
        )
        if not app:
            app = self.env["connect.voicetel.voiceml"].create(
                {
                    "model": "connect.voicetel.domain",
                    "method": "route_call",
                    "code_type": "model_method",
                    "name": "SIP Domains calls",
                    "description": "Required application!",
                }
            )
        return app

    def create_voicetel_sip_domain(self, client):
        self.ensure_one()
        domain = client.sip.domains.create(
            friendly_name=self.friendly_name,
            domain_name=self.domain_name,
            voice_url=self.application.voice_url,
            voice_fallback_url=self.application.voice_fallback_url,
            sip_registration=True,
            voice_status_callback_url=self.application.voice_status_url,
        )
        # One credential list per domain, mapped for both REGISTER and
        # INVITE authentication.
        credential_list = client.sip.credential_lists.create(friendly_name=domain.sid)
        client.sip.domains.auth.registrations.credential_list_mappings(
            domain.sid).create(credential_list_sid=credential_list.sid)
        client.sip.domains.auth.calls.credential_list_mappings(
            domain.sid).create(credential_list_sid=credential_list.sid)
        self.write(
            {
                "sid": domain.sid,
                "cred_list_sid": credential_list.sid,
            }
        )
        debug(self, "Domain {} was created".format(self.friendly_name))
        self._create_user_credentials_for_domain(client)
        return domain

    def _create_user_credentials_for_domain(self, client=None):
        """Create SIP credentials in VoiceML for the SIP-enabled users of this domain."""
        self.ensure_one()
        if not self.sid or not self.cred_list_sid:
            debug(self, "Cannot create user credentials: domain not properly created in VoiceML")
            return
        client = client or self.env["connect.settings"].get_voicetel_client()
        domain_users = self.env['connect.user'].sudo().search([
            ('voicetel_domain', '=', self.id),
            ('voicetel_sip_enabled', '=', True),
            ('voicetel_sid', '=', False),
        ])
        debug(self, "Found {} SIP-enabled users for domain {}".format(
            len(domain_users), self.friendly_name))
        for user in domain_users:
            try:
                password = user.voicetel_password or self.env[
                    'connect.user'].generate_voicetel_password()
                credential = client.sip.credential_lists.credentials(
                    self.cred_list_sid
                ).create(
                    username=user.voicetel_username,
                    password=password
                )
                user.with_context(skip_voicetel_sync=True).write({
                    'voicetel_sid': credential.sid,
                    'voicetel_password': password,
                })
                debug(self, "Created SIP credential for user {}".format(
                    user.voicetel_username))
            except Exception as e:
                debug(self, "Error creating SIP credential for user {}: {}".format(
                    user.voicetel_username, str(e)), level="error")

    def _import_existing_domain_by_name(self, client=None):
        """Adopt a domain that already exists in the account under this name.

        Re-creating a taken domain is what left orphans behind in the
        earlier Twilio-module attempt; the record is pointed at the
        existing resource and its credential list instead.
        """
        self.ensure_one()
        client = client or self.env["connect.settings"].get_voicetel_client()
        try:
            matching_domain = None
            for domain in client.sip.domains.iter():
                if domain.domain_name == self.domain_name:
                    matching_domain = domain
                    break
            if not matching_domain:
                raise ValidationError(
                    "Domain name '{}' is already used by another VoiceML "
                    "account. Please choose a different label.".format(
                        self.domain_name)
                )
            register_mappings = client.sip.domains.auth.registrations \
                .credential_list_mappings(matching_domain.sid).list().credential_list_mappings
            calls_mappings = client.sip.domains.auth.calls \
                .credential_list_mappings(matching_domain.sid).list().credential_list_mappings
            cred_list_sid = None
            if register_mappings:
                # The mapping SID is the credential list SID.
                cred_list_sid = register_mappings[0].sid
            elif calls_mappings:
                cred_list_sid = calls_mappings[0].sid
            if not cred_list_sid:
                credential_list = client.sip.credential_lists.create(
                    friendly_name=matching_domain.sid)
                cred_list_sid = credential_list.sid
            if not register_mappings:
                client.sip.domains.auth.registrations \
                    .credential_list_mappings(matching_domain.sid).create(
                        credential_list_sid=cred_list_sid)
            if not calls_mappings:
                client.sip.domains.auth.calls \
                    .credential_list_mappings(matching_domain.sid).create(
                        credential_list_sid=cred_list_sid)
            self.write({
                'sid': matching_domain.sid,
                'cred_list_sid': cred_list_sid,
            })
            self.update_voicetel_domain(client)
            self._import_sip_credentials_from_voicetel(client, cred_list_sid)
        except ValidationError:
            raise
        except Exception as e:
            debug(self, "Error importing domain by name: {}".format(str(e)), level="error")
            raise ValidationError(
                "Failed to import existing domain '{}': {}".format(
                    self.domain_name, format_connect_response(e)
                )
            )

    def _import_sip_credentials_from_voicetel(self, client, cred_list_sid):
        """Reconcile the credential list with the domain's Odoo users.

        Credentials that exist only in VoiceML get a connect.user row (no
        password is readable, the admin sets one); SIP-enabled users missing
        from the list get a credential created.
        """
        self.ensure_one()
        try:
            credentials = client.sip.credential_lists.credentials(
                cred_list_sid).iter()
            domain_users = self.env['connect.user'].sudo().search(
                [('voicetel_domain', '=', self.id)])
            sip_enabled_users = domain_users.filtered(lambda u: u.voicetel_sip_enabled)
            voicetel_usernames = {cred.username for cred in credentials}
            odoo_usernames = {user.voicetel_username for user in sip_enabled_users}
            for credential in credentials:
                matching_user = domain_users.filtered(
                    lambda u: u.voicetel_username == credential.username)
                if matching_user:
                    matching_user.with_context(skip_voicetel_sync=True).write({
                        'voicetel_sid': credential.sid,
                        'voicetel_sip_enabled': True,
                    })
                else:
                    self.env['connect.user'].sudo().with_context(
                        no_voicetel_create=True,
                        skip_voicetel_sync=True
                    ).create({
                        'voicetel_sid': credential.sid,
                        'voicetel_username': credential.username,
                        'voicetel_sip_enabled': True,
                        'voicetel_domain': self.id,
                    })
            for username in odoo_usernames - voicetel_usernames:
                odoo_user = sip_enabled_users.filtered(
                    lambda u: u.voicetel_username == username)[:1]
                if not odoo_user:
                    continue
                try:
                    password = odoo_user.voicetel_password or self.env[
                        'connect.user'].generate_voicetel_password()
                    credential = client.sip.credential_lists.credentials(
                        cred_list_sid).create(
                            username=username, password=password)
                    odoo_user.with_context(skip_voicetel_sync=True).write({
                        'voicetel_sid': credential.sid,
                        'voicetel_password': password,
                    })
                except Exception as e:
                    debug(self, "Error creating VoiceML credential for user {}: {}".format(
                        username, str(e)), level="error")
        except Exception as e:
            debug(self, "Error importing SIP credentials: {}".format(str(e)), level="error")
            logger.warning("Failed to import SIP credentials for domain %s: %s",
                           self.friendly_name, str(e))

    def create_domain(self, client):
        self.ensure_one()
        try:
            self.application = self.get_domain_app()
            self.create_voicetel_sip_domain(client)
        except Exception as e:
            if _domain_taken(e):
                self._import_existing_domain_by_name(client)
            else:
                raise ValidationError(format_connect_response(e))

    @api.model_create_multi
    def create(self, vals_list):
        rec = super().create(vals_list)
        if not self.env.context.get("no_voicetel_create"):
            client = self.env["connect.settings"].get_voicetel_client()
            for domain in rec:
                domain.create_domain(client)
        return rec

    def unlink(self):
        for rec in self:
            if rec.delete_protection and not self.env.context.get('force_delete'):
                raise ValidationError("Remove delete protection to delete the domain!")
        if not self.env["connect.settings"].get_param("voicetel_auto_sync"):
            return super().unlink()
        client = self.env["connect.settings"].get_voicetel_client()
        for rec in self:
            if not rec.sid:
                continue
            try:
                if rec.cred_list_sid:
                    client.sip.domains.auth.registrations.credential_list_mappings(
                        rec.sid).delete(rec.cred_list_sid)
                    client.sip.domains.auth.calls.credential_list_mappings(
                        rec.sid).delete(rec.cred_list_sid)
                    client.sip.credential_lists.delete(rec.cred_list_sid)
                client.sip.domains.delete(rec.sid)
                debug(self, "Domain removed.")
            except Exception as e:
                if "not found" in str(e):
                    pass
                else:
                    raise ValidationError(format_connect_response(e))
        return super().unlink()

    def update_voicetel_domain(self, client):
        self.ensure_one()
        try:
            client.sip.domains.update(
                self.sid,
                friendly_name=self.friendly_name,
                voice_url=self.application.voice_url,
                voice_fallback_url=self.application.voice_fallback_url,
                voice_status_callback_url=self.application.voice_status_url,
            )
            debug(self, "Domain {} updated".format(self.friendly_name))
        except Exception as e:
            if "not found" in str(e):
                logger.warning(
                    "VoiceML domain %s not found, creating.", self.friendly_name
                )
                self.create_domain(client)
            elif _domain_taken(e):
                raise ValidationError("This domain name is already used in VoiceML!")
            else:
                raise

    def write(self, vals):
        if not self.env["connect.settings"].get_param("voicetel_auto_sync"):
            return super().write(vals)
        if not (
            set(["friendly_name", "subdomain", "application"]) & set(vals.keys())
        ):
            return super().write(vals)
        res = super().write(vals)
        client = self.env["connect.settings"].get_voicetel_client()
        try:
            for rec in self:
                if rec.sid:
                    rec.update_voicetel_domain(client)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(format_connect_response(e))
        return res

    @api.model
    def sync(self):
        """Sync domains between Odoo and VoiceML.

        Rules:
        1. Do NOT import records that exist only in VoiceML
        2. Create in VoiceML what exists only in Odoo (handles account migration)
        3. Update what exists in both
        """
        client = self.env["connect.settings"].get_voicetel_client()
        voicetel_sids = set([k.sid for k in client.sip.domains.iter()])
        odoo_records = self.search([])
        odoo_sids = {sid for sid in odoo_records.mapped("sid") if sid}
        only_in_odoo = odoo_sids - voicetel_sids
        common_recs = odoo_sids & voicetel_sids
        debug(self, "Only in Odoo domain SIDs: {}".format(only_in_odoo))
        for domain in odoo_records.filtered(lambda d: not d.sid or d.sid in only_in_odoo):
            debug(self, "Creating domain {} in VoiceML...".format(domain.friendly_name))
            domain.create_domain(client)
        for domain in odoo_records.filtered(lambda d: d.sid in common_recs):
            domain.update_voicetel_domain(client)

    @api.model
    def _sip_user_part(self, value):
        """User part of a SIP address, else the value itself."""
        if not isinstance(value, str):
            return value
        found = re.search(r"^(?:sips?:)?([^@]+)@", value)
        return found.group(1) if found else value

    @api.model
    def route_call(self, request, params=None):
        """Route a call placed from a device registered on a SIP domain."""
        params = dict(params or {})
        if not self.env["oduist.license"].check_license('connect'):
            return '<Response><Say>Service unavailable.</Say></Response>'
        debug(self, "Domain call to %s" % request.get("To"))
        # Create call + channel
        self.env["connect.call"].on_voicetel_call_status(request)
        # A blind transfer points the other party's leg back at this same
        # application with the destination in `forward_to`, so that a
        # forwarded call is routed by exactly the rules below rather than by a
        # parallel implementation.
        to_val = request.get("forward_to") or request.get("To") or ''
        found_num = self._sip_user_part(to_val)
        exten = self.env["connect.voicetel.exten"].sudo().search(
            [("number", "=", found_num)], limit=1)
        if not exten:
            # Match by pattern; an extension number may be written in E.164.
            all_extensions = self.env["connect.voicetel.exten"].sudo().search([])
            matching_extensions = all_extensions.filtered(
                lambda x: x.number and re.match(
                    r"^{}$".format(re.escape(x.number)), found_num or '')
            )
            if len(matching_extensions) > 1:
                logger.error(
                    "Multiple extensions %s found for number %s",
                    matching_extensions, found_num)
                return "<Response><Say>Multiple extensions found. Check your dialplan. Goodbye! </Say></Response>"
            elif len(matching_extensions) == 1:
                exten = matching_extensions[0]
        if exten:
            return exten.render(request=request, params=params)
        elif isinstance(found_num, str) and found_num.startswith("+"):
            return self.originate_external_call(found_num, request, params=params)
        else:
            return "<Response><Say>Extension not found. Goodbye! </Say></Response>"

    def originate_external_call(self, number, request, params=None):
        debug(self, "Outgoing call to %s" % number)
        default_number = self.env["connect.voicetel.outgoing_callerid"].sudo().search(
            [("is_default", "=", True)], limit=1
        )
        user = self.env["connect.user"].get_user_by_uri(request.get("Caller"))
        if user and user.voicetel_outgoing_callerid:
            callerId = user.voicetel_outgoing_callerid.number
        else:
            callerId = default_number.number if default_number else False
        if not callerId:
            return "<Response><Say>You must select a default number for caller ID!</Say></Response>"
        settings = self.env['connect.settings'].sudo()
        response = VoiceResponse()
        status_url = settings.voicetel_webhook_url("voicetel/webhook/callstatus")
        record_status_url = settings.voicetel_webhook_url("voicetel/webhook/recordingstatus")
        call_duration_limit = int(settings.get_param('call_duration_limit'))
        if user and user.record_calls:
            dial = Dial(
                timeout=60,
                callerId=callerId,
                timeLimit=call_duration_limit,
                record="record-from-answer",
                recordingStatusCallback=record_status_url,
            )
        else:
            dial = Dial(timeout=60, callerId=callerId, timeLimit=call_duration_limit)
        dial.number(
            number,
            statusCallback=status_url,
            statusCallbackEvent="initiated answered completed",
        )
        response.append(dial)
        debug(self, "Originate external: %s" % pretty_xml(str(response)))
        return response
