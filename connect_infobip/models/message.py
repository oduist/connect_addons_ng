# -*- coding: utf-8 -*-
import ast
import logging
import re

from markupsafe import Markup

from odoo import models, api, fields, SUPERUSER_ID
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

FAILED_STATUSES = ['undeliverable', 'expired', 'rejected']

DLR_STATUS_MAP = {
    'pending': 'sent',
    'delivered': 'delivered',
    'undeliverable': 'undeliverable',
    'expired': 'expired',
    'rejected': 'rejected',
}


class ConnectMessage(models.Model):
    _inherit = 'connect.message'

    infobip_bulk_id = fields.Char(readonly=True)

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        """Override: check Infobip numbers and WhatsApp senders to
        determine direction.

        Known limitation (ADR-032/ADR-036): co-installing several
        messaging provider modules leaves the last-loaded module owning
        this compute and send() until a core dispatcher hook exists.
        """
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                our_numbers = self.env['connect.infobip.number'].search(
                    []).mapped('phone_number')
                our_whatsapp = self.env[
                    'connect.infobip.whatsapp_sender'
                ].search([]).mapped('number')
                all_our_numbers = set(our_numbers) | set(our_whatsapp)
                if rec.from_number in all_our_numbers:
                    rec.direction = 'outgoing'
                else:
                    rec.direction = 'incoming'

    @api.model
    def _infobip_format_number(self, number):
        """Infobip carries MSISDNs without the + prefix; the ledger and the
        number models store E.164 with it."""
        if not number:
            return number
        number = str(number)
        if re.match(r'^[0-9]+$', number):
            return '+{}'.format(number)
        return number

    @api.model
    def _infobip_message_values(self, result):
        """Map one inbound SMS result to connect.message values."""
        return {
            'message_sid': result.get('messageId'),
            'from_number': self._infobip_format_number(result.get('from')),
            'to_number': self._infobip_format_number(result.get('to')),
            'body': result.get('cleanText') or result.get('text'),
            'num_media': 0,
            'status': 'received',
            'message_type': 'sms',
        }

    @api.model
    def _infobip_whatsapp_values(self, result):
        """Map one inbound WhatsApp result (typed message object)."""
        message = result.get('message') or {}
        values = {
            'message_sid': result.get('messageId'),
            'from_number': self._infobip_format_number(result.get('from')),
            'to_number': self._infobip_format_number(result.get('to')),
            'body': message.get('text') or message.get('caption') or '',
            'num_media': 0,
            'status': 'received',
            'message_type': 'WhatsApp',
        }
        if message.get('url'):
            values.update({
                'media_url': message.get('url'),
                'num_media': 1,
            })
        return values

    @api.model
    def infobip_receive(self, event):
        """Process the inbound SMS webhook ({"results": [...]} envelope,
        Numbers API forward-to-HTTP)."""
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return ''
        try:
            for result in event.get('results') or []:
                logger.info('Received Infobip SMS webhook data:\n%s', result)
                self._infobip_dispatch_inbound(
                    self._infobip_message_values(result))
        except Exception as e:
            logger.error('Error handling incoming message: %s', e)
        return ''

    @api.model
    def infobip_receive_whatsapp(self, event):
        """Process the inbound WhatsApp webhook (same results envelope,
        typed message payloads)."""
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return ''
        try:
            for result in event.get('results') or []:
                logger.info(
                    'Received Infobip WhatsApp webhook data:\n%s', result)
                self._infobip_dispatch_inbound(
                    self._infobip_whatsapp_values(result))
        except Exception as e:
            logger.error('Error handling incoming WhatsApp message: %s', e)
        return ''

    @api.model
    def _infobip_dispatch_inbound(self, values):
        """Shared inbound tail: threading, message_configuration routing,
        chatter. Line-for-line port of the Telnyx message.received branch
        (ADR-033 shapes)."""
        from_number = values.get('from_number')
        to_number = values.get('to_number')
        partner = self.env['res.partner'].get_partner_by_number(from_number)
        if partner:
            values.update({'partner': partner.id})
        # Determine parent and target: thread on the last message
        # exchanged with this correspondent.
        last_message = self.env['connect.message'].search(
            [
                ('from_number', '=', to_number),
                ('to_number', '=', from_number),
            ],
            order='create_date desc',
            limit=1,
        )
        target_msg = last_message
        valid_target = False
        if (
            target_msg
            and target_msg.res_model
            and target_msg.res_id
        ):
            target_rec = (
                self.env[target_msg.res_model]
                .sudo()
                .browse(target_msg.res_id)
            )
            if target_rec.exists():
                values.update(
                    {
                        'res_model': target_msg.res_model,
                        'res_id': target_msg.res_id,
                    }
                )
                valid_target = True
            else:
                logger.warning(
                    'Target record %s(%s) does not exist anymore',
                    target_msg.res_model,
                    target_msg.res_id,
                )
                target_msg = False
        message = self.env['connect.message'].sudo().create(values)
        # Message destination handling
        if not target_msg:
            target_msg = message
            valid_target = True
            config = self.env[
                'connect.infobip.message_configuration'
            ].sudo().search(
                [('number.phone_number', '=', to_number)], limit=1
            )
            dest_model = (
                config.destination
                if config and config.destination
                else 'res.partner'
            )
            defaults = {}
            if config and config.default_values:
                try:
                    defaults = dict(
                        ast.literal_eval(
                            config.default_values or '{}'
                        )
                    )
                except Exception as e:
                    logger.error(
                        'Invalid default data: %s\n%s',
                        config.default_values,
                        e,
                    )
            if dest_model in self.env:
                try:
                    new_rec = (
                        self.env[dest_model]
                        .with_context(
                            mail_create_nosubscribe=True
                        )
                        .sudo()
                        .create_record_from_message(
                            message, default_values=defaults
                        )
                    )
                    target_msg.write(
                        {
                            'res_model': dest_model,
                            'res_id': new_rec.id,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        'create_record_from_message failed for %s: %s',
                        dest_model,
                        e,
                    )
            else:
                logger.warning(
                    'Destination model %s not found', dest_model
                )
        # Add message to chatter
        if (
            valid_target
            and target_msg
            and target_msg.res_model
            and target_msg.res_id
        ):
            obj = (
                self.env[target_msg.res_model]
                .with_user(SUPERUSER_ID)
                .browse(target_msg.res_id)
            )
            if obj.exists() and hasattr(obj, 'message_post'):
                body = Markup(
                    "<div class='d-flex flex-row px-1'>"
                    "<span class='px-1'>{}</span></div>".format(
                        values.get('body')
                    )
                )
                if message.media_url:
                    body = Markup(
                        "<div class='d-flex flex-row'>"
                        "<span class='px-1'>{}</span>"
                        "<br/>{}</div>".format(
                            values.get('body'),
                            message.media_widget,
                        )
                    )
                link = Markup(
                    '<small><a href="/web#id={}&model=connect.message&view_type=form">'
                    'Message</a></small>'.format(message.id)
                )
                body = Markup(str(body) + str(link))
                mt_comment = self.env.ref('mail.mt_comment').id
                kwargs = {
                    'body': body,
                    'subtype_id': mt_comment,
                    'message_type': message.message_type,
                }
                if partner:
                    kwargs.update({'author_id': partner.id})
                chatter = obj.with_context(
                    mail_create_nosubscribe=True
                ).message_post(**kwargs)
                chatter.connect_message = message
                self.env[
                    'connect.settings'
                ].connect_reload_view(target_msg.res_model)
        return message

    @api.model
    def infobip_process_delivery_report(self, event):
        """Unified SMS + WhatsApp delivery report handler. SMS reports
        arrive via the per-send notifyUrl; WhatsApp DLR forwarding is
        pointed at the same URL on the Infobip side (ADR-036)."""
        try:
            for result in event.get('results') or []:
                logger.info('Received Infobip delivery report:\n%s', result)
                message = self.env['connect.message'].sudo().search(
                    [('message_sid', '=', result.get('messageId'))], limit=1)
                if not message:
                    continue
                status_info = result.get('status') or {}
                group = (status_info.get('groupName') or '').lower()
                if not group:
                    continue
                message.update(
                    {'status': DLR_STATUS_MAP.get(group, group)})
                if group in FAILED_STATUSES:
                    error = result.get('error') or {}
                    message.update(
                        {
                            'error_code': str(
                                error.get('id') or error.get('name') or ''),
                            'error_message': (error.get('description')
                                              or status_info.get('description')),
                            'has_error': True,
                        }
                    )
                    # Mirror the Twilio status-callback UX: surface the
                    # failure in the chatter of the related record.
                    if (message.message_type == 'WhatsApp'
                            and message.res_model and message.res_id):
                        connect_partner = self.env.ref(
                            'connect.user_connect_webhook').partner_id
                        sender = self.env[
                            'connect.infobip.whatsapp_sender'
                        ].search([], limit=1)
                        if sender:
                            sender.chatter_post(
                                message.res_model, message.res_id,
                                connect_partner.id,
                                'Failed to send this WhatsApp message')
        except Exception as e:
            logger.error('Error handling delivery report: %s', e)
        return ''

    def send(
        self,
        recipient,
        body,
        res_id=None,
        res_model=None,
        outgoing_callerid=None,
        **kwargs,
    ):
        if self.env['connect.settings']._get_message_provider() != 'infobip':
            return super().send(
                recipient, body, res_id=res_id, res_model=res_model,
                outgoing_callerid=outgoing_callerid, **kwargs)
        self.env['oduist.license'].check_license('connect', silent=False)
        sender_user = self.env.user
        message_data = {
            'message_type': 'sms',
            'to_number': recipient,
            'body': body,
            'sender_user': sender_user.id,
            'res_id': res_id,
            'res_model': res_model,
            'status': 'sent',
        }
        if outgoing_callerid:
            sender = outgoing_callerid
        else:
            number = sender_user.connect_user.infobip_outgoing_callerid
            if not number:
                raise ValidationError(
                    'You dont have an outgoing callerid number!'
                )
            sender = number.number
        result = self.infobip_client_send(recipient, sender, body)
        if result is False:
            raise ValidationError(
                'Unexpected error! Contact admin or maintainer!'
            )
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        status_info = result.get('status') or {}
        group = (status_info.get('groupName') or '').lower()
        message_data.update(
            {
                'from_number': sender,
                'partner': partner.id,
                'message_sid': result.get('messageId'),
                'infobip_bulk_id': result.get('bulkId'),
            }
        )
        if group in FAILED_STATUSES:
            message_data.update(
                {
                    'status': DLR_STATUS_MAP.get(group, group),
                    'error_code': str(status_info.get('id') or ''),
                    'error_message': status_info.get('description'),
                    'has_error': True,
                }
            )
        message = self.env['connect.message'].sudo().create(message_data)
        # Add message to chatter
        if res_model and res_id:
            mt_note = self.env.ref('mail.mt_note').id
            obj = (
                self.env[res_model]
                .with_user(SUPERUSER_ID)
                .browse(res_id)
            )
            if hasattr(obj, 'message_post'):
                link = Markup(
                    '<small><a href="/web#id={}&model=connect.message&view_type=form">'
                    'Message</a></small>'.format(message.id)
                )
                chat_body = Markup(str(body) + '<br/>' + str(link))
                kwargs = {
                    'body': chat_body,
                    'subtype_id': mt_note,
                    'message_type': message.message_type,
                }
                kwargs.update(
                    {'author_id': sender_user.partner_id.id}
                )
                chatter = obj.with_context(
                    mail_create_nosubscribe=True
                ).message_post(**kwargs)
                mail_notification_values = [
                    {
                        'author_id': chatter.author_id.id,
                        'mail_message_id': chatter.id,
                        'res_partner_id': chatter.author_id.id,
                        'sms_number': sender,
                        'notification_type': message.message_type,
                        'is_read': True,
                        'notification_status': 'ready',
                    }
                ]
                self.env['mail.notification'].sudo().create(
                    mail_notification_values
                )
                self.env['connect.settings'].connect_reload_view(
                    res_model
                )

    def infobip_client_send(self, recipient, sender, body):
        """Send one SMS via /sms/2/text/advanced. The per-message notifyUrl
        delivers DLRs without account-level subscription setup (ADR-036).
        Returns the first messages[] entry (with bulkId) or False."""
        Settings = self.env['connect.settings']
        payload = {
            'messages': [{
                # Infobip expects MSISDNs without the + prefix.
                'from': (sender or '').lstrip('+'),
                'destinations': [{'to': (recipient or '').lstrip('+')}],
                'text': body,
                'notifyUrl': Settings.get_infobip_webhook_url(
                    'message_status'),
                'notifyContentType': 'application/json',
                'intermediateReport': True,
            }]
        }
        try:
            response = Settings.infobip_api_request(
                'POST', '/sms/2/text/advanced', payload)
        except Exception as e:
            logger.exception(e)
            return False
        messages = response.get('messages') or []
        result = dict(messages[0]) if messages else {}
        result['bulkId'] = response.get('bulkId')
        logger.info('Message to %s is sent.', recipient)
        return result

    def action_retry(self):
        for rec in self:
            if rec.status not in ['failed'] + FAILED_STATUSES:
                continue
            try:
                self.env['connect.message'].send(
                    recipient=rec.to_number,
                    body=rec.body or '',
                    res_id=rec.res_id or None,
                    res_model=rec.res_model or None,
                    outgoing_callerid=rec.from_number or None,
                )
            except ValidationError:
                raise
            except Exception as e:
                logger.exception(
                    'Retry send failed for message %s: %s', rec.id, e
                )
        return True
