# -*- coding: utf-8 -*-

import logging
import random
import re
import string
from urllib.parse import urljoin
from odoo import fields, models, api, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response
from .texml_response import Dial, VoiceResponse, pretty_xml


logger = logging.getLogger(__name__)


class Domain(models.Model):
    """The Telnyx analog of a Twilio SIP domain (ADR-032).

    One record manages two Telnyx resources:
    - a credential connection (`sid`) hosting per-user telephony
      credentials (SIP registration + WebRTC clients);
    - the routing TeXML application (`application`) whose
      inbound.sip_subdomain is this record's subdomain, so calls dialed
      to sip:<dst>@<subdomain>.sip.telnyx.com from the account's own
      connections are routed by Odoo (route_call).
    """
    _name = "connect.telnyx.domain"
    _rec_name = "friendly_name"
    _description = "Telnyx Domain"
    _order = "friendly_name"

    sid = fields.Char("Credential Connection ID", readonly=True)
    application = fields.Many2one(
        "connect.telnyx.texml",
        ondelete="restrict",
        required=True,
        default=lambda self: self.get_domain_app(),
    )
    connection_username = fields.Char(
        readonly=True,
        help="Connection-level SIP username generated for the Telnyx "
             "credential connection. Users register with their own "
             "telephony credentials, not with this account.")
    subdomain = fields.Char(required=True)
    domain_name = fields.Char(compute="_get_domain_name")
    friendly_name = fields.Char(required=True)
    sip_registration = fields.Boolean("SIP Registration", readonly=True, default=True)
    delete_protection = fields.Boolean(default=True)

    if release.version_info[0] >= 19:
        _uniq_subdomain = Constraint(
            'UNIQUE(subdomain)', 'This subdomain is already used!')
    else:
        _sql_constraints = [
            ("uniq_subdomain", "UNIQUE(subdomain)", "This subdomain is already used!")
        ]

    def _get_domain_name(self):
        for rec in self:
            if rec.subdomain:
                rec.domain_name = rec.subdomain + ".sip.telnyx.com"
            else:
                rec.domain_name = ''

    def get_domain_app(self):
        # Domain must be created.
        app = self.env["connect.telnyx.texml"].search(
            [
                ("code_type", "=", "model_method"),
                ("model", "=", "connect.telnyx.domain"),
                ("method", "=", "route_call"),
            ],
            limit=1,
        )
        if not app:
            # Who removed that!?
            app = self.env["connect.telnyx.texml"].create(
                {
                    "model": "connect.telnyx.domain",
                    "method": "route_call",
                    "code_type": "model_method",
                    "name": "SIP Domains calls",
                    "description": "Required application!",
                }
            )
        return app

    @staticmethod
    def _generate_connection_credentials(subdomain):
        username = '{}{}'.format(
            re.sub(r'[^a-zA-Z0-9]', '', subdomain)[:20],
            ''.join(random.choices(string.digits, k=6)))
        password_chars = [
            random.choice(string.ascii_lowercase),
            random.choice(string.ascii_uppercase),
            random.choice(string.digits),
        ]
        all_chars = string.ascii_letters + string.digits
        password_chars += random.choices(all_chars, k=16 - len(password_chars))
        random.shuffle(password_chars)
        return username, ''.join(password_chars)

    def _set_app_subdomain(self, client, subdomain=None):
        """Push the SIP subdomain onto the routing TeXML application."""
        self.ensure_one()
        app = self.application
        if not app.sid:
            app.update_telnyx_app(client)
        client.texml_applications.update(
            app.sid,
            friendly_name=app.name,
            voice_url=app.voice_url,
            inbound={
                'sip_subdomain': subdomain if subdomain is not None else self.subdomain,
                'sip_subdomain_receive_settings': 'only_my_connections',
            },
        )

    def create_telnyx_domain(self, client):
        self.ensure_one()
        username, password = self._generate_connection_credentials(self.subdomain)
        connection = client.credential_connections.create(
            connection_name=self.friendly_name,
            user_name=username,
            password=password,
        )
        self.write(
            {
                "sid": connection.data.id,
                "connection_username": username,
            }
        )
        self._set_app_subdomain(client)
        debug(self, "Domain {} was created".format(self.friendly_name))

        # Create telephony credentials for existing users in this domain
        self._create_user_credentials_for_domain(client)

        return connection.data

    def _create_user_credentials_for_domain(self, client=None):
        """Create telephony credentials in Telnyx for all connect.user
        records related to this domain."""
        self.ensure_one()
        if not self.sid:
            debug(self, "Cannot create user credentials: domain not properly created in Telnyx")
            return

        client = client or self.env["connect.settings"].get_telnyx_client()

        domain_users = self.env['connect.user'].search([
            ('telnyx_domain', '=', self.id),
            '|',
            ('telnyx_sip_enabled', '=', True),
            ('telnyx_client_enabled', '=', True),
        ])

        debug(self, "Found {} Telnyx-enabled users for domain {}".format(
            len(domain_users), self.friendly_name))

        for user in domain_users:
            try:
                user._ensure_telnyx_credentials(client=client)
            except Exception as e:
                debug(self, "Error creating Telnyx credential for user {}: {}".format(
                    user.name, str(e)), level="error")

    def create_domain(self, client):
        self.ensure_one()
        try:
            # Create app first if required.
            self.application = self.get_domain_app()
            # Create the credential connection and set the subdomain.
            self.create_telnyx_domain(client)
        except Exception as e:
            if "already exists" in str(e) or "must be unique" in str(e):
                raise ValidationError('The subdomain is already used in Telnyx!')
            else:
                ret = format_connect_response(e)
                raise ValidationError(ret)

    @api.model_create_multi
    def create(self, vals_list):
        rec = super().create(vals_list)
        if not self.env.context.get("no_telnyx_create"):
            client = self.env["connect.settings"].get_telnyx_client()
            rec.create_domain(client)
        return rec

    def unlink(self):
        for rec in self:
            if rec.delete_protection and not self.env.context.get('force_delete'):
                raise ValidationError("Remove delete protection to delete the domain!")
        if not self.env["connect.settings"].get_param("telnyx_auto_sync"):
            return super().unlink()

        client = self.env["connect.settings"].get_telnyx_client()
        for rec in self:
            try:
                # Detach the subdomain from the routing app, then remove
                # the credential connection (its telephony credentials are
                # removed by Telnyx together with the connection).
                rec._set_app_subdomain(client, subdomain='')
                if rec.sid:
                    client.credential_connections.delete(rec.sid)
                debug(self, "Domain removed.")
            except Exception as e:
                if "not found" in str(e).lower() or '404' in str(e):
                    # Domain was removed from Telnyx, remove here.
                    pass
                else:
                    raise ValidationError(format_connect_response(e))
        return super().unlink()

    def update_telnyx_domain(self, client):
        self.ensure_one()
        try:
            client.credential_connections.update(
                self.sid,
                connection_name=self.friendly_name,
            )
            self._set_app_subdomain(client)
            debug(self, "Domain {} updated".format(self.friendly_name))
        except Exception as e:
            if "not found" in str(e).lower() or '404' in str(e):
                logger.warning(
                    "Telnyx domain %s not found, creating.", self.friendly_name
                )
                self.create_domain(client)
            elif "already exists" in str(e) or "must be unique" in str(e):
                raise ValidationError("This subdomain is already used in Telnyx!")
            else:
                raise

    def write(self, vals):
        if not self.env["connect.settings"].get_param("telnyx_auto_sync"):
            return super().write(vals)
        # Update only Telnyx fields.
        if not (
            set(["friendly_name", "domain_name", "subdomain", "application"]) & set(vals.keys())
        ):
            return super().write(vals)
        res = super().write(vals)
        client = self.env["connect.settings"].get_telnyx_client()
        # Iterate over records and update Telnyx.
        try:
            for rec in self:
                rec.update_telnyx_domain(client)
        except Exception as e:
            raise ValidationError(format_connect_response(e))
        return res

    @api.model
    def sync(self):
        """Sync domains between Odoo and Telnyx.

        Rules:
        1. Do NOT import records that exist only in Telnyx
        2. Create in Telnyx what exists only in Odoo (handles account migration)
        3. Update what exists in both
        """
        client = self.env["connect.settings"].get_telnyx_client()
        telnyx_records = list(client.credential_connections.list())
        telnyx_sids = set([k.id for k in telnyx_records])
        odoo_records = self.search([])
        odoo_sids = {sid for sid in set(odoo_records.mapped("sid")) if sid}

        only_in_telnyx = telnyx_sids - odoo_sids
        debug(self, "Only in Telnyx connection IDs (ignoring): {}".format(only_in_telnyx))
        only_in_odoo = odoo_sids - telnyx_sids
        debug(self, "Only in Odoo connection IDs: {}".format(only_in_odoo))
        common_recs = odoo_sids & telnyx_sids
        debug(self, "Common connection IDs: {}".format(common_recs))

        for sid in only_in_odoo:
            odoo_domain = self.search([("sid", "=", sid)])
            if odoo_domain:
                debug(self, "Creating domain {} in Telnyx account...".format(odoo_domain.friendly_name))
                try:
                    old_sid = sid
                    odoo_domain.create_telnyx_domain(client)
                    debug(self, "Domain {} migrated: old ID {}, new ID {}".format(
                        odoo_domain.friendly_name, old_sid, odoo_domain.sid))
                except Exception as e:
                    raise ValidationError("Error creating domain {} in Telnyx: {}".format(
                        odoo_domain.friendly_name, format_connect_response(str(e))))

        for sid in common_recs:
            odoo_domain = self.search([("sid", "=", sid)])
            if odoo_domain:
                odoo_domain.update_telnyx_domain(client)

    @api.model
    def route_call(self, request, params={}):
        if not self.env["oduist.license"].check_license('connect'):
            return '<Response><Say>Service unavailable.</Say></Response>'
        debug(self, "Domain call to %s" % request.get("To"))
        # Create call + channel
        self.env["connect.call"].on_telnyx_call_status(request)
        to_val = request.get("To") or ''
        # Extract the dialed number from the SIP URI
        found = re.search(r"^sip:(.+?)@(.+)\.sip\.telnyx\.com", to_val)
        if found:
            found_num = found.group(1)
        else:
            found_num = to_val
        exten = self.env["connect.telnyx.exten"].sudo().search([("number", "=", found_num)])
        if not exten:
            # Get all extensions and match by pattern.
            all_extensions = self.env["connect.telnyx.exten"].sudo().search([])
            # Handle case of extension number is defined as E1.64 (with +).
            matching_extensions = all_extensions.filtered(
                lambda x: re.match(
                    r"^{}$".format(
                        "\\" + x.number if x.number.startswith("+") else x.number
                    ),
                    found_num,
                )
            )
            if len(matching_extensions) > 1:
                logger.error(
                    "Multiple extensions %s found for number %s",
                    matching_extensions,
                    found_num,
                )
                return "<Response><Say>Multiple extensions found. Check your dialplan. Goodbye! </Say></Response>"
            elif len(matching_extensions) == 1:
                exten = matching_extensions[0]
        if exten:
            # Render extensions dialplan
            res = exten.render(request=request, params=params)
            return res
        elif isinstance(found_num, str) and found_num.startswith("+"):
            return self.originate_external_call(found_num, request, params=params)
        else:
            return "<Response><Say>Extension not found. Goodbye! </Say></Response>"

    def originate_external_call(self, number, request, params={}):
        debug(self, "Outgoing call to %s" % number)
        default_number = self.env["connect.telnyx.outgoing_callerid"].search(
            [("is_default", "=", True)], limit=1
        )
        # Find the user by caller.
        user = self.env["connect.user"].get_user_by_telnyx_uri(request.get("Caller"))
        if user and user.telnyx_outgoing_callerid:
            callerId = user.telnyx_outgoing_callerid.number
        else:
            callerId = default_number.number if default_number else False
        if not callerId:
            return "<Response><Say>You must select a default number for caller ID!</Say></Response>"
        response = VoiceResponse()
        api_url = self.env["connect.settings"].get_param("api_url")
        status_url = urljoin(api_url, "telnyx/webhook/callstatus")
        record_status_url = urljoin(api_url, "telnyx/webhook/recordingstatus")
        call_duration_limit = int(self.env['connect.settings'].sudo().get_param('call_duration_limit'))
        if user.record_calls:
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
