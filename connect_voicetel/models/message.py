# -*- coding: utf-8 -*-
import ast
import logging

from markupsafe import Markup
from .voiceml_response import MessagingResponse

from odoo import models, fields, api, SUPERUSER_ID, release
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ConnectMessage(models.Model):
    _inherit = 'connect.message'

    voicetel_account_sid = fields.Char('VoiceML Account SID')

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        """Override: a message from one of our VoiceTel numbers is outgoing."""
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                our_numbers = self.env['connect.voicetel.number'].sudo().search(
                    []).mapped('phone_number')
                if rec.from_number in set(our_numbers):
                    rec.direction = 'outgoing'
                else:
                    super(ConnectMessage, rec)._compute_direction()

    @api.model
    def voicetel_receive(self, params):
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return str(MessagingResponse())
        try:
            if params.get('AccountSid') != self.env[
                'connect.settings'
            ].sudo().get_param('voicetel_account_sid'):
                logger.warning(
                    "Received VoiceML SMS webhook with incorrect AccountSid"
                )
                return str(MessagingResponse())
            if params.get('SmsStatus') == 'received':
                logger.info(
                    "Received VoiceTel SMS webhook data:\n%s", params
                )
                from_number = params.get('From')
                to_number = params.get('To')
                values = self.get_receive_message_values(params)
                values.update({'message_type': 'sms'})
                # Media handling
                try:
                    if int(params.get('NumMedia', '0') or 0) > 0:
                        values.update(
                            {
                                'media_url': params.get('MediaUrl0'),
                                'media_content_type': params.get(
                                    'MediaContentType0'
                                ),
                            }
                        )
                except Exception:
                    pass
                partner = self.env[
                    'res.partner'
                ].get_partner_by_number(from_number)
                if partner:
                    values.update({'partner': partner.id})
                # Determine parent and target
                original_sid = (
                    params.get('OriginalRepliedMessageSid')
                    or params.get('originalrepliedmessagesid')
                    or next(
                        (
                            params[k]
                            for k in params.keys()
                            if str(k).lower()
                            == 'originalrepliedmessagesid'
                        ),
                        None,
                    )
                )
                parent_msg = False
                if original_sid:
                    parent_msg = self.env['connect.message'].search(
                        [('message_sid', '=', original_sid)], limit=1
                    )
                last_message = False
                if not parent_msg:
                    last_message = self.env['connect.message'].search(
                        [
                            ('from_number', '=', to_number),
                            ('to_number', '=', from_number),
                        ],
                        order='create_date desc',
                        limit=1,
                    )
                target_msg = parent_msg or last_message
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
                if parent_msg:
                    values.update({'parent_message': parent_msg.id})
                message = (
                    self.env['connect.message'].sudo().create(values)
                )
                # Message destination handling
                if not target_msg:
                    target_msg = message
                    valid_target = True
                    # sudo: this runs as the webhook user, and the routing
                    # configuration is deliberately admin-only, so an
                    # unprivileged read raised AccessError and the except
                    # below swallowed it -- the whole inbound message was
                    # dropped with only "Error handling incoming SMS" logged.
                    config = self.env[
                        'connect.voicetel.message_configuration'
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
                        mt_comment = self.env.ref(
                            'mail.mt_comment'
                        ).id
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
            else:
                # Update message status
                logger.info(
                    "Received Update VoiceTel SMS webhook data:\n%s", params
                )
                message = (
                    self.env['connect.message']
                    .sudo()
                    .search(
                        [
                            (
                                'message_sid',
                                '=',
                                params.get('MessageSid'),
                            )
                        ]
                    )
                )
                status = params.get('MessageStatus') or params.get('SmsStatus')
                message.update({'status': status})
                if status in ('failed', 'undelivered'):
                    values = {
                        'error_code': params.get('ErrorCode'),
                        'has_error': True,
                    }
                    # VoiceML does not send ErrorMessage on status callbacks.
                    if params.get('ErrorMessage'):
                        values['error_message'] = params.get('ErrorMessage')
                    message.update(values)
        except Exception as e:
            logger.error("Error handling incoming SMS: %s", e)
        return str(MessagingResponse())

    def send(
        self,
        recipient,
        body,
        res_id=None,
        res_model=None,
        outgoing_callerid=None,
        **kwargs,
    ):
        if self.env['connect.settings']._get_message_provider() != 'voicetel':
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
            number = sender_user.connect_user.voicetel_outgoing_callerid
            if not number:
                raise ValidationError(
                    'You dont have an outgoing callerid number!'
                )
            sender = number.number
        message = self.voicetel_client_send(recipient, sender, body)
        if not message:
            raise ValidationError(
                'Unexpected error! Contact admin or maintainer!'
            )
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        message_data.update(
            {
                'voicetel_account_sid': message.account_sid,
                'from_number': sender,
                'partner': partner.id,
                'num_media': message.num_media,
                'error_code': message.error_code,
                'error_message': message.error_message,
                'message_sid': message.sid,
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

    def voicetel_client_send(self, recipient, sender, body):
        try:
            settings = self.env['connect.settings'].sudo()
            client = settings.get_voicetel_client()
            message = client.messages.create(
                to=recipient,
                from_=sender,
                body=body,
                status_callback=settings.voicetel_webhook_url(
                    'voicetel/webhook/message'),
            )
            if message.error_code:
                logger.error('VoiceML refused the message to %s: %s %s',
                             recipient, message.error_code, message.error_message)
                return False
            logger.info('Message to %s is sent.', recipient)
            return message
        except Exception as e:
            logger.exception(e)
            return False

    def action_retry(self):
        for rec in self:
            if rec.status != 'failed':
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
