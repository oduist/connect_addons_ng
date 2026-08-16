# -*- coding: utf-8 -*-
import ast
import logging

from markupsafe import Markup

from odoo import models, api, SUPERUSER_ID
from odoo.exceptions import ValidationError

from .settings import format_connect_response

logger = logging.getLogger(__name__)

FAILED_STATUSES = ['sending_failed', 'delivery_failed']


class ConnectMessage(models.Model):
    _inherit = 'connect.message'

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        """Override: check Telnyx numbers and WhatsApp senders to
        determine direction.

        Known limitation (ADR-032): co-installing connect_twilio and
        connect_telnyx leaves the last-loaded module owning this compute
        and send() until a core dispatcher hook exists.
        """
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                our_numbers = self.env['connect.telnyx.number'].search([]).mapped(
                    'phone_number'
                )
                our_whatsapp = self.env[
                    'connect.telnyx.whatsapp_sender'
                ].search([]).mapped('number')
                all_our_numbers = set(our_numbers) | set(our_whatsapp)
                if rec.from_number in all_our_numbers:
                    rec.direction = 'outgoing'
                else:
                    rec.direction = 'incoming'

    @api.model
    def _telnyx_message_type(self, payload):
        """Map the Telnyx payload type to the connect.message type."""
        payload_type = (payload.get('type') or '').lower()
        if payload_type == 'whatsapp':
            return 'WhatsApp'
        if payload_type == 'rcs':
            return 'RCS'
        return 'sms'

    @api.model
    def _telnyx_message_values(self, payload):
        """Map a Telnyx v2 message payload to connect.message values."""
        from_info = payload.get('from', {}) or {}
        to_list = payload.get('to', []) or []
        to_info = to_list[0] if to_list else {}
        media = payload.get('media', []) or []
        values = {
            'message_sid': payload.get('id'),
            'from_number': from_info.get('phone_number'),
            'to_number': to_info.get('phone_number'),
            'body': payload.get('text'),
            'num_media': len(media),
            'status': 'received',
        }
        if media:
            values.update({
                'media_url': media[0].get('url'),
                'media_content_type': media[0].get('content_type'),
            })
        return values

    @api.model
    def telnyx_receive(self, event):
        """Process a Telnyx messaging webhook (v2 JSON envelope)."""
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return ''
        try:
            data = event.get('data', {}) or {}
            event_type = data.get('event_type')
            payload = data.get('payload', {}) or {}
            if event_type == 'message.received':
                logger.info("Received Telnyx message webhook data:\n%s", payload)
                values = self._telnyx_message_values(payload)
                values['message_type'] = self._telnyx_message_type(payload)
                from_number = values.get('from_number')
                to_number = values.get('to_number')
                partner = self.env['res.partner'].get_partner_by_number(
                    from_number)
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
                        'connect.telnyx.message_configuration'
                    ].search(
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
            elif event_type in ['message.sent', 'message.finalized']:
                # Update message status
                logger.info(
                    "Received Telnyx message status webhook:\n%s", payload)
                to_list = payload.get('to', []) or []
                status = to_list[0].get('status') if to_list else False
                message = (
                    self.env['connect.message']
                    .sudo()
                    .search(
                        [('message_sid', '=', payload.get('id'))]
                    )
                )
                if not message or not status:
                    return ''
                message.update({'status': status})
                if status in FAILED_STATUSES:
                    errors = payload.get('errors') or []
                    error = errors[0] if errors else {}
                    message.update(
                        {
                            'error_code': error.get('code'),
                            'error_message': error.get('title'),
                            'has_error': True,
                        }
                    )
                    # Mirror the Twilio status-callback UX: surface the
                    # failure in the chatter of the related record.
                    if (message.message_type in ['WhatsApp', 'RCS']
                            and message.res_model and message.res_id):
                        connect_partner = self.env.ref(
                            "connect.user_connect_webhook").partner_id
                        sender_model = (
                            'connect.telnyx.whatsapp_sender'
                            if message.message_type == 'WhatsApp'
                            else 'connect.telnyx.rcs_agent')
                        sender = self.env[sender_model].search([], limit=1)
                        if sender:
                            sender.chatter_post(
                                message.res_model, message.res_id,
                                connect_partner.id,
                                'Failed to send this {} message'.format(
                                    message.message_type))
        except Exception as e:
            logger.error("Error handling incoming message: %s", e)
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
        if self.env['connect.settings']._get_message_provider() != 'telnyx':
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
            number = sender_user.connect_user.telnyx_outgoing_callerid
            if not number:
                # Same fallback as click-to-call: the account default.
                number = self.env['connect.telnyx.outgoing_callerid'].search(
                    [('is_default', '=', True)], limit=1)
            if not number:
                raise ValidationError(
                    'You dont have an outgoing callerid number!'
                )
            sender = number.number
        message = self.telnyx_client_send(recipient, sender, body)
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        errors = getattr(message, 'errors', None) or []
        error = errors[0] if errors else None
        message_data.update(
            {
                'from_number': sender,
                'partner': partner.id,
                'num_media': len(getattr(message, 'media', None) or []),
                'error_code': getattr(error, 'code', None) if error else False,
                'error_message': getattr(error, 'title', None) if error else False,
                'message_sid': message.id,
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

    def telnyx_client_send(self, recipient, sender, body):
        try:
            client = self.env['connect.settings'].get_telnyx_client()
            response = client.messages.send(
                to=recipient,
                from_=sender,
                text=body,
            )
            message = response.data
            logger.info('Message to %s is sent.', recipient)
        except Exception as e:
            # Surface the provider error: "invalid from address",
            # "number not in the messaging profile" and friends are
            # actionable, "unexpected error" is not.
            logger.exception('Cannot send a Telnyx message:')
            raise ValidationError(
                'Unable to send the message: {}'.format(
                    format_connect_response(e)))
        if not message or not message.id:
            raise ValidationError(
                'The Telnyx API did not return a message ID.')
        return message

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
