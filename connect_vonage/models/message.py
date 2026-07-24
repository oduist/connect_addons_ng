# -*- coding: utf-8 -*-
import ast
import json
import logging

from markupsafe import Markup

from odoo import models, api, SUPERUSER_ID
from odoo.exceptions import ValidationError

from vonage_messages import Sms

from odoo.addons.connect.models.settings import debug
from .settings import (
    format_connect_response,
    lock_vonage_webhook,
    to_e164,
    to_vonage_number,
)

logger = logging.getLogger(__name__)

MEDIA_CONTENT_TYPES = {
    'image': 'image/jpeg',
    'audio': 'audio/mpeg',
    'video': 'video/mp4',
    'file': 'application/octet-stream',
}


class ConnectMessage(models.Model):
    _inherit = 'connect.message'

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        """Override: check own Vonage numbers for direction."""
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                our_numbers = self.env['connect.number'].search([]).mapped(
                    'phone_number')
                if rec.from_number in set(our_numbers):
                    rec.direction = 'outgoing'
                else:
                    rec.direction = 'incoming'

    @api.model
    def get_vonage_message_values(self, params):
        """Map a Messages API v1 inbound webhook to connect.message vals."""
        channel = params.get('channel') or 'sms'
        message_type = 'WhatsApp' if channel == 'whatsapp' else channel
        values = {
            'message_sid': params.get('message_uuid'),
            'from_number': to_e164(params.get('from')),
            'to_number': to_e164(params.get('to')),
            'body': params.get('text'),
            'status': 'received',
            'message_type': message_type,
        }
        content_type = params.get('message_type')
        media = params.get(content_type) if content_type else None
        if isinstance(media, dict) and media.get('url'):
            values.update({
                'num_media': 1,
                'media_url': media.get('url'),
                'media_content_type': MEDIA_CONTENT_TYPES.get(
                    content_type, 'application/octet-stream'),
            })
            if not values['body'] and media.get('caption'):
                values['body'] = media.get('caption')
        return values

    @api.model
    def receive(self, params):
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return True
        message_uuid = params.get('message_uuid')
        if not message_uuid:
            logger.error('Inbound Vonage message has no message_uuid.')
            return False
        lock_vonage_webhook(self.env.cr, 'message', message_uuid)
        if self.sudo().search_count(
                [('message_sid', '=', message_uuid)], limit=1):
            return True
        try:
            debug(self, 'Receive message: %s' % json.dumps(params, indent=2))
            values = self.get_vonage_message_values(params)
            from_number = values['from_number']
            to_number = values['to_number']
            partner = self.env['res.partner'].get_partner_by_number(
                from_number)
            if partner:
                values.update({'partner': partner.id})
            # Determine parent and target for threading
            original_uuid = (params.get('context') or {}).get('message_uuid')
            parent_msg = False
            if original_uuid:
                parent_msg = self.env['connect.message'].search(
                    [('message_sid', '=', original_uuid)], limit=1)
            last_message = False
            if not parent_msg:
                last_message = self.env['connect.message'].search(
                    [('from_number', '=', to_number),
                     ('to_number', '=', from_number)],
                    order='create_date desc', limit=1)
            target_msg = parent_msg or last_message
            valid_target = False
            if target_msg and target_msg.res_model and target_msg.res_id:
                target_rec = self.env[target_msg.res_model].sudo().browse(
                    target_msg.res_id)
                if target_rec.exists():
                    values.update({
                        'res_model': target_msg.res_model,
                        'res_id': target_msg.res_id,
                    })
                    valid_target = True
                else:
                    logger.warning(
                        'Target record %s(%s) does not exist anymore',
                        target_msg.res_model, target_msg.res_id)
                    target_msg = False
            if parent_msg:
                values.update({'parent_message': parent_msg.id})
            message = self.env['connect.message'].sudo().create(values)
            # Message destination handling
            if not target_msg:
                target_msg = message
                valid_target = True
                config = self.env['connect.message_configuration'].search(
                    [('number.phone_number', '=', to_number)], limit=1)
                dest_model = (
                    config.destination
                    if config and config.destination else 'res.partner')
                defaults = {}
                if config and config.default_values:
                    try:
                        defaults = dict(ast.literal_eval(
                            config.default_values or '{}'))
                    except Exception as e:
                        logger.error(
                            'Invalid default data: %s\n%s',
                            config.default_values, e)
                if dest_model in self.env:
                    try:
                        new_rec = self.env[dest_model].with_context(
                            mail_create_nosubscribe=True,
                        ).sudo().create_record_from_message(
                            message, default_values=defaults)
                        target_msg.write({
                            'res_model': dest_model,
                            'res_id': new_rec.id,
                        })
                    except Exception as e:
                        logger.warning(
                            'create_record_from_message failed for %s: %s',
                            dest_model, e)
                else:
                    logger.warning(
                        'Destination model %s not found', dest_model)
            # Add message to chatter
            if (valid_target and target_msg and target_msg.res_model
                    and target_msg.res_id):
                obj = self.env[target_msg.res_model].with_user(
                    SUPERUSER_ID).browse(target_msg.res_id)
                if obj.exists() and hasattr(obj, 'message_post'):
                    body = Markup(
                        "<div class='d-flex flex-row px-1'>"
                        "<span class='px-1'>{}</span></div>".format(
                            values.get('body')))
                    if message.media_url:
                        body = Markup(
                            "<div class='d-flex flex-row'>"
                            "<span class='px-1'>{}</span>"
                            "<br/>{}</div>".format(
                                values.get('body'), message.media_widget))
                    link = Markup(
                        '<small><a href="/web#id={}&model=connect.message'
                        '&view_type=form">Message</a></small>'.format(
                            message.id))
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
                        mail_create_nosubscribe=True).message_post(**kwargs)
                    chatter.connect_message = message
                    self.env['connect.settings'].connect_reload_view(
                        target_msg.res_model)
        except Exception as e:
            logger.exception('Error handling incoming message: %s', e)
        return True

    @api.model
    def update_message_status(self, params):
        self = self.sudo()
        debug(self, 'Message status: %s' % json.dumps(params, indent=2))
        message = self.search(
            [('message_sid', '=', params.get('message_uuid'))], limit=1)
        if not message:
            logger.warning(
                'Status for unknown message %s', params.get('message_uuid'))
            return False
        status = params.get('status')
        vals = {'status': status}
        if status in ('rejected', 'undeliverable'):
            error = params.get('error') or {}
            vals.update({
                'has_error': True,
                'error_code': str(error.get('type') or status),
                'error_message': error.get('title') or error.get('detail'),
            })
        message.write(vals)
        return True

    def send(self, recipient, body, res_id=None, res_model=None,
             outgoing_callerid=None):
        self.env['oduist.license'].check_license('connect', silent=False)
        sender_user = self.env.user
        if outgoing_callerid:
            sender = outgoing_callerid
        else:
            number = sender_user.connect_user.outgoing_callerid
            if not number:
                raise ValidationError(
                    'You dont have an outgoing callerid number!')
            sender = number.number
        client = self.env['connect.settings'].get_client()
        try:
            response = client.messages.send(Sms(
                to=to_vonage_number(recipient),
                from_=to_vonage_number(sender),
                text=body,
            ))
        except Exception as e:
            logger.exception('Vonage message send error:')
            raise ValidationError(format_connect_response(e))
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        message_data = {
            'message_type': 'sms',
            'message_sid': response.message_uuid,
            'from_number': sender,
            'to_number': recipient,
            'body': body,
            'sender_user': sender_user.id,
            'partner': partner.id,
            'res_id': res_id,
            'res_model': res_model,
            'status': 'sent',
        }
        message = self.env['connect.message'].sudo().create(message_data)
        # Add message to chatter
        if res_model and res_id:
            mt_note = self.env.ref('mail.mt_note').id
            obj = self.env[res_model].with_user(SUPERUSER_ID).browse(res_id)
            if hasattr(obj, 'message_post'):
                link = Markup(
                    '<small><a href="/web#id={}&model=connect.message'
                    '&view_type=form">Message</a></small>'.format(message.id))
                chat_body = Markup(str(body) + '<br/>' + str(link))
                kwargs = {
                    'body': chat_body,
                    'subtype_id': mt_note,
                    'message_type': message.message_type,
                }
                kwargs.update({'author_id': sender_user.partner_id.id})
                chatter = obj.with_context(
                    mail_create_nosubscribe=True).message_post(**kwargs)
                mail_notification_values = [{
                    'author_id': chatter.author_id.id,
                    'mail_message_id': chatter.id,
                    'res_partner_id': chatter.author_id.id,
                    'sms_number': sender,
                    'notification_type': message.message_type,
                    'is_read': True,
                    'notification_status': 'ready',
                }]
                self.env['mail.notification'].sudo().create(
                    mail_notification_values)
                self.env['connect.settings'].connect_reload_view(res_model)

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
                    'Retry send failed for message %s: %s', rec.id, e)
        return True
