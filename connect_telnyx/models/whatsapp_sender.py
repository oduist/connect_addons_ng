# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

from markupsafe import Markup

from odoo import models, fields, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

logger = logging.getLogger(__name__)


class TelnyxWhatsappSender(models.Model):
    """WhatsApp-enabled Telnyx phone numbers (senders).

    Mirrors the Twilio connect.whatsapp_sender shape (ADR-033). Telnyx
    addresses WhatsApp with plain +E.164 numbers — no whatsapp: prefix.
    """
    _name = 'connect.telnyx.whatsapp_sender'
    _description = 'Telnyx WhatsApp Sender'
    _rec_name = 'number'
    _order = 'number'

    # Core identifiers
    number = fields.Char(required=True, help="Sender phone in E.164, e.g., +1234567890", readonly=True)
    phone_number_id = fields.Char(string='Phone Number ID', index=True, readonly=True)
    waba_id = fields.Char(string='Business Account ID', readonly=True)
    status = fields.Char(readonly=True)

    # Convenience fields
    number_id = fields.Many2one('connect.telnyx.number', string='Linked Number', ondelete='set null',
                                help='Matched by phone number if available.', readonly=True)

    # Profile (editable — pushed back to Telnyx on save)
    display_name = fields.Char(string='Display Name', readonly=True)
    profile_about = fields.Char(string='About')
    profile_address = fields.Char(string='Address')
    profile_description = fields.Text(string='Description')
    profile_email = fields.Char(string='Email')
    profile_website = fields.Char(string='Website')

    # Properties
    quality_rating = fields.Char(string='Quality Rating', readonly=True)
    calling_enabled = fields.Boolean(string='WhatsApp Calling Enabled', readonly=True,
        help='Informational only — WhatsApp voice is not integrated (ADR-033).')

    # Local controls
    no_sync = fields.Boolean(string='Do not sync', default=False)
    is_default = fields.Boolean(string='Default WhatsApp Sender', help='Used as default when user has no personal sender set.')

    if release.version_info[0] >= 19:
        _number_unique = Constraint('UNIQUE(number)', 'This number already exists!')
    else:
        _sql_constraints = [
            ('number_unique', 'UNIQUE(number)', 'This number already exists!'),
        ]

    @api.constrains('is_default')
    def _check_single_default(self):
        for rec in self:
            if rec.is_default:
                others = self.search([('is_default', '=', True), ('id', '!=', rec.id)], limit=1)
                if others:
                    raise ValidationError('Only one WhatsApp sender can be marked as default.')

    def _prepare_vals_from_api(self, item):
        vals = {
            'number': item.get('phone_number'),
            'phone_number_id': item.get('phone_number_id'),
            'waba_id': item.get('waba_id'),
            'status': item.get('status'),
            'display_name': item.get('display_name'),
            'quality_rating': item.get('quality_rating'),
            'calling_enabled': bool(item.get('calling_enabled')),
        }
        if vals.get('number'):
            linked = self.env['connect.telnyx.number'].search(
                [('phone_number', '=', vals['number'])], limit=1)
            if linked:
                vals['number_id'] = linked.id
        return vals

    def _fetch_profile(self, client=None):
        self.ensure_one()
        try:
            # The WhatsApp resources of the Telnyx SDK prefix their paths
            # with /v2 while the client base URL already ends in /v2, so
            # these endpoints are called through the settings helper.
            response = self.env['connect.settings'].telnyx_api_request(
                'GET', 'whatsapp/phone_numbers/{}/profile'.format(self.number))
            profile = response.get('data') or {}
            self.with_context(skip_telnyx_sync=True).write({
                'profile_about': profile.get('about'),
                'profile_address': profile.get('address'),
                'profile_description': profile.get('description'),
                'profile_email': profile.get('email'),
                'profile_website': profile.get('website'),
            })
        except Exception as e:
            debug(self, 'Cannot fetch WhatsApp profile for {}: {}'.format(
                self.number, e), level='warning')

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('skip_telnyx_sync'):
            return res
        if not self.env['connect.settings'].get_param('telnyx_auto_sync'):
            return res
        profile_fields = {'profile_about', 'profile_address', 'profile_description',
                          'profile_email', 'profile_website'}
        if not (profile_fields & set(vals.keys())):
            return res
        for rec in self:
            try:
                self.env['connect.settings'].telnyx_api_request(
                    'PATCH',
                    'whatsapp/phone_numbers/{}/profile'.format(rec.number),
                    payload={
                        'about': rec.profile_about or '',
                        'address': rec.profile_address or '',
                        'description': rec.profile_description or '',
                        'email': rec.profile_email or '',
                        'website': rec.profile_website or '',
                    },
                )
                debug(self, 'WhatsApp profile for {} updated.'.format(rec.number))
            except Exception as e:
                raise ValidationError(format_connect_response(e))
        return res

    @api.model
    def sync(self):
        try:
            response = self.env['connect.settings'].telnyx_api_request(
                'GET', 'whatsapp/phone_numbers')
            items = response.get('data') or []
        except Exception as e:
            raise ValidationError("Failed to sync WhatsApp Senders: {}".format(
                format_connect_response(e)))
        seen_numbers = set()
        for item in items:
            number = item.get('phone_number')
            if not number:
                continue
            seen_numbers.add(number)
            vals = self._prepare_vals_from_api(item)
            rec = self.search([('number', '=', number)], limit=1)
            if rec:
                # Respect local no_sync flag: skip updating this record
                if rec.no_sync:
                    continue
                rec.with_context(skip_telnyx_sync=True).write(vals)
                debug(self, 'Updated a WhatsApp sender {}'.format(rec.number))
            else:
                rec = self.with_context(skip_telnyx_sync=True).create([vals])[0]
                debug(self, 'Created a WhatsApp sender {}'.format(rec.number))
            rec._fetch_profile()
        # Remove local senders missing in Telnyx
        missing = self.search([('number', 'not in', list(seen_numbers))]) if seen_numbers \
            else self.search([])
        if missing:
            debug(self, 'Removing missing WhatsApp Senders: {}'.format(', '.join(
                [k.number for k in missing])))
            missing.unlink()
        self.env['connect.settings'].connect_notify('WhatsApp Senders synced')

    def action_sync(self):
        self.sync()
        return True

    @api.model
    def get_default_sender(self, user=None):
        """Return the default WhatsApp sender.
        Preference order:
        - Given user's connect_user.telnyx_whatsapp_sender_id
        - Current env user's connect_user.telnyx_whatsapp_sender_id
        - Sender with is_default = True
        - Any available sender
        """
        connect_user = False
        try:
            if user and getattr(user, '_name', '') == 'connect.user':
                connect_user = user
            elif user and getattr(user, '_name', '') == 'res.users':
                connect_user = user.connect_user
            else:
                connect_user = self.env.user.connect_user
        except Exception:
            connect_user = False
        if connect_user and connect_user.telnyx_whatsapp_sender_id:
            return connect_user.telnyx_whatsapp_sender_id
        default = self.search([('is_default', '=', True)], limit=1)
        if default:
            return default
        return self.search([], limit=1)

    def _check_conversation_window(self, recipient):
        """Freeform sends need an inbound WhatsApp message from the
        recipient within 24 hours (same local heuristic as
        connect_twilio, ADR-033)."""
        last_incoming = self.env['connect.message'].sudo().search([
            ('message_type', '=', 'WhatsApp'),
            ('from_number', '=', recipient),
            ('direction', '=', 'incoming')
        ], order='create_date desc', limit=1)
        if not last_incoming:
            debug(self, 'No inbound WhatsApp message from {} found, a template is required.'.format(recipient))
            raise ValidationError(
                '24 hours contact window has been expired. '
                'Please select a message template to initiate a new contact window.'
            )
        if datetime.now() - last_incoming.create_date > timedelta(hours=24):
            raise ValidationError(
                '24 hours contact window has been expired. '
                'Please select a message template to initiate a new contact window.'
            )
        debug(self, 'Inbound WhatsApp message within 24 hours found, freeform send allowed.')

    def send_whatsapp(self, recipient, body, res_model=None, res_id=None,
                      raise_on_error=True, template=None, template_variables=None):
        """Send a WhatsApp message using this sender and create
        connect.message + chatter.

        Args:
            recipient (str): E.164 phone (e.g., +123456789).
            body (str): Message text (preview text when a template is used).
            res_model (str): Optional model to post to chatter.
            res_id (int): Optional record id to post to chatter.
            raise_on_error (bool): When True raise ValidationError on failures.
            template (connect.telnyx.whatsapp_template): Optional approved template.
            template_variables (list): Ordered body parameter values for the template.
        Returns:
            connect.message record or False on error when raise_on_error=False
        """
        self.ensure_one()
        self.env['oduist.license'].check_license('connect', silent=False)
        if not self.number:
            raise ValidationError('WhatsApp sender has no number configured.')
        if not template:
            self._check_conversation_window(recipient)
        client = self.env['connect.settings'].get_telnyx_client()
        if template:
            whatsapp_message = {
                'type': 'template',
                'template': template._as_message_template(template_variables),
            }
        else:
            whatsapp_message = {
                'type': 'text',
                'text': {'body': body or ''},
            }
        try:
            response = client.messages.whatsapp(
                from_=self.number,
                to=recipient,
                whatsapp_message=whatsapp_message,
                type='WHATSAPP',
            )
            message = response.data
        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    'Unable to send WhatsApp message: {}'.format(
                        format_connect_response(e)))
            logger.error('Unable to send WhatsApp message to %s via %s: %s',
                         recipient, self.number, e)
            return False
        if not message or not message.id:
            if raise_on_error:
                raise ValidationError('WhatsApp API did not return a message ID.')
            logger.error('WhatsApp API did not return a message ID for recipient %s', recipient)
            return False

        # Create connect.message record mirroring ConnectMessage.send
        sender_user = self.env.user
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        errors = getattr(message, 'errors', None) or []
        error = errors[0] if errors else None
        msg_vals = {
            'message_type': 'WhatsApp',
            'to_number': recipient,
            'from_number': self.number,
            'body': body,
            'sender_user': sender_user.id,
            'partner': partner.id if partner else False,
            'res_model': res_model,
            'res_id': res_id,
            'status': 'sent',
            'error_code': getattr(error, 'code', None) if error else False,
            'error_message': getattr(error, 'title', None) if error else False,
            'message_sid': message.id,
        }
        msg = self.env['connect.message'].sudo().create(msg_vals)

        # Post to chatter if relevant
        if res_model and res_id:
            chatter_message = Markup(f"<div class='d-flex flex-row'>"
                                     f"<p class='px-1'>{body}</p></div>")
            self.chatter_post(res_model, res_id, self.env.user.partner_id.id, chatter_message)
        return msg

    def chatter_post(self, res_model, res_id, author, body):
        try:
            mt_note = self.env.ref('mail.mt_note').id
            obj = self.env[res_model].browse(res_id)
            if hasattr(obj, 'message_post'):
                chatter = obj.sudo().with_context(mail_create_nosubscribe=True).message_post(
                    body=body,
                    subtype_id=mt_note,
                    message_type='WhatsApp',
                    author_id=author,
                )
                self.env['mail.notification'].sudo().create([{
                    'author_id': chatter.author_id.id,
                    'mail_message_id': chatter.id,
                    'res_partner_id': chatter.author_id.id,
                    'sms_number': self.number,
                    'notification_type': 'WhatsApp',
                    'is_read': True,
                    'notification_status': 'ready',
                }])
                self.env['connect.settings'].connect_reload_view(res_model)
        except Exception as e:
            logger.warning('Failed to post WhatsApp chatter message on %s,%s: %s', res_model, res_id, e)
