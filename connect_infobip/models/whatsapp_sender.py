# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta

from markupsafe import Markup

from odoo import models, fields, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class InfobipWhatsappSender(models.Model):
    """WhatsApp-enabled Infobip senders.

    Mirrors the Twilio/Telnyx whatsapp_sender shape (ADR-033). Senders are
    registered in the Infobip portal and readonly-synced here (ADR-036);
    Infobip addresses WhatsApp with plain E.164 numbers — no whatsapp:
    prefix.
    """
    _name = 'connect.infobip.whatsapp_sender'
    _description = 'Infobip WhatsApp Sender'
    _rec_name = 'number'
    _order = 'number'

    number = fields.Char(
        required=True, readonly=True,
        help='Sender phone in E.164, e.g., +1234567890')
    status = fields.Char(readonly=True)
    waba_id = fields.Char(string='Business Account ID', readonly=True)
    quality_rating = fields.Char(string='Quality Rating', readonly=True)
    number_id = fields.Many2one(
        'connect.infobip.number', string='Linked Number', ondelete='set null',
        help='Matched by phone number if available.', readonly=True)
    no_sync = fields.Boolean(string='Do not sync', default=False)
    is_default = fields.Boolean(
        string='Default WhatsApp Sender',
        help='Used as default when user has no personal sender set.')

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
                others = self.search(
                    [('is_default', '=', True), ('id', '!=', rec.id)], limit=1)
                if others:
                    raise ValidationError(
                        'Only one WhatsApp sender can be marked as default.')

    @api.model
    def _prepare_vals_from_api(self, item):
        number = (item.get('sender') or item.get('phoneNumber')
                  or item.get('number') or '')
        if number and not str(number).startswith('+'):
            number = '+{}'.format(number)
        vals = {
            'number': number,
            'status': item.get('status') or '',
            'waba_id': (item.get('businessAccountId')
                        or item.get('wabaId') or False),
            'quality_rating': (item.get('qualityRating')
                               or item.get('quality') or False),
        }
        if number:
            linked = self.env['connect.infobip.number'].search(
                [('phone_number', '=', number)], limit=1)
            if linked:
                vals['number_id'] = linked.id
        return vals

    @api.model
    def sync(self):
        # The senders listing endpoint shape must be confirmed live
        # (ADR-036); infobip_sync() treats a failure here as non-fatal.
        response = self.env['connect.settings'].infobip_api_request(
            'GET', '/whatsapp/1/senders')
        items = (response.get('senders') or response.get('results') or [])
        seen_numbers = set()
        for item in items:
            vals = self._prepare_vals_from_api(item)
            if not vals.get('number'):
                continue
            seen_numbers.add(vals['number'])
            rec = self.search([('number', '=', vals['number'])], limit=1)
            if rec:
                # Respect local no_sync flag: skip updating this record
                if rec.no_sync:
                    continue
                rec.write(vals)
                debug(self, 'Updated a WhatsApp sender {}'.format(rec.number))
            else:
                rec = self.create([vals])[0]
                debug(self, 'Created a WhatsApp sender {}'.format(rec.number))
        # Remove local senders missing in Infobip
        missing = self.search([('number', 'not in', list(seen_numbers))]) \
            if seen_numbers else self.search([])
        if missing:
            debug(self, 'Removing missing WhatsApp Senders: {}'.format(
                ', '.join([k.number for k in missing])))
            missing.unlink()
        self.env['connect.settings'].connect_notify('WhatsApp Senders synced')

    def action_sync(self):
        self.sync()
        return True

    @api.model
    def get_default_sender(self, user=None):
        """Return the default WhatsApp sender.
        Preference order:
        - Given user's connect_user.infobip_whatsapp_sender_id
        - Current env user's connect_user.infobip_whatsapp_sender_id
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
        if connect_user and connect_user.infobip_whatsapp_sender_id:
            return connect_user.infobip_whatsapp_sender_id
        default = self.search([('is_default', '=', True)], limit=1)
        if default:
            return default
        return self.search([], limit=1)

    def _check_conversation_window(self, recipient):
        """Freeform sends need an inbound WhatsApp message from the
        recipient within 24 hours (same local heuristic as
        connect_twilio/connect_telnyx, ADR-033)."""
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
            template (connect.infobip.whatsapp_template): Optional approved template.
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
        Settings = self.env['connect.settings']
        sender_msisdn = self.number.lstrip('+')
        recipient_msisdn = (recipient or '').lstrip('+')
        message_id = False
        try:
            if template:
                response = Settings.infobip_api_request(
                    'POST', '/whatsapp/1/message/template',
                    {
                        'messages': [{
                            'from': sender_msisdn,
                            'to': recipient_msisdn,
                            'content': template._as_message_content(
                                template_variables),
                        }],
                    })
                messages = response.get('messages') or []
                message_id = (messages[0].get('messageId')
                              if messages else False)
            else:
                response = Settings.infobip_api_request(
                    'POST', '/whatsapp/1/message/text',
                    {
                        'from': sender_msisdn,
                        'to': recipient_msisdn,
                        'content': {'text': body or ''},
                    })
                message_id = response.get('messageId')
        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    'Unable to send WhatsApp message: {}'.format(e))
            logger.error('Unable to send WhatsApp message to %s via %s: %s',
                         recipient, self.number, e)
            return False
        if not message_id:
            if raise_on_error:
                raise ValidationError('WhatsApp API did not return a message ID.')
            logger.error('WhatsApp API did not return a message ID for recipient %s', recipient)
            return False

        # Create connect.message record mirroring ConnectMessage.send
        sender_user = self.env.user
        partner = self.env['res.partner'].get_partner_by_number(recipient)
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
            'message_sid': message_id,
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
