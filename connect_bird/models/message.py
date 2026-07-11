# -*- coding: utf-8 -*-
import ast
import logging

from markupsafe import Markup

from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Normalize Bird message statuses to the core display vocabulary. Statuses
# not listed here are stored as-is (sent, delivered, scheduled, ...).
BIRD_MESSAGE_STATUS_MAP = {
    'accepted': 'sent',
    'processing': 'sent',
    'delivery_failed': 'failed',
    'sending_failed': 'failed',
    'skipped': 'failed',
    'deleted': 'canceled',
}
BIRD_FAILED_STATUSES = ('delivery_failed', 'sending_failed', 'skipped')


class ConnectMessage(models.Model):
    _inherit = 'connect.message'

    bird_message_id = fields.Char('Bird Message ID', index=True, readonly=True)
    bird_channel = fields.Many2one(
        'connect.bird.channel', ondelete='set null', readonly=True)

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        """Override: also check Bird channel identifiers for direction."""
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                our_numbers = set(
                    self.env['connect.bird.channel'].search([]).mapped('identifier'))
                if rec.from_number in our_numbers:
                    rec.direction = 'outgoing'
                else:
                    super(ConnectMessage, rec)._compute_direction()

    @api.model
    def _map_bird_message_status(self, status):
        return BIRD_MESSAGE_STATUS_MAP.get(status, status)

    @api.model
    def _get_bird_sender_channels(self, outgoing_callerid=None):
        """Ordered candidate sender channels: an explicit choice disables
        fallback; automatic selection tries WhatsApp first, then SMS.
        """
        Channel = self.env['connect.bird.channel']
        if outgoing_callerid:
            if isinstance(outgoing_callerid, models.BaseModel):
                return [outgoing_callerid]
            channel = Channel.search([
                '|', ('identifier', '=', outgoing_callerid),
                ('sid', '=', outgoing_callerid),
                ('platform_id', 'in', ('sms', 'whatsapp')),
            ], limit=1)
            if not channel:
                raise ValidationError(
                    'No Bird channel matches sender {}!'.format(outgoing_callerid))
            return [channel]
        user_channel = self.env.user.connect_user.bird_message_channel
        if user_channel:
            return [user_channel]
        channels = []
        for platform in ('whatsapp', 'sms'):
            try:
                channels.append(Channel.get_default_channel(platform))
            except ValidationError:
                continue
        if not channels:
            raise ValidationError(
                'No active Bird message channel. Run Sync in Bird Settings '
                'and check your channels!')
        return channels

    def send(self, recipient, body, res_id=None, res_model=None,
             outgoing_callerid=None, **kwargs):
        if self.env['connect.settings']._get_message_provider() != 'bird':
            return super().send(
                recipient, body, res_id=res_id, res_model=res_model,
                outgoing_callerid=outgoing_callerid, **kwargs)
        return self.send_bird(
            recipient, body, res_id=res_id, res_model=res_model,
            outgoing_callerid=outgoing_callerid)

    def send_bird(self, recipient, body, res_id=None, res_model=None,
                  outgoing_callerid=None):
        """Bird transport, callable directly (bypassing the provider
        dispatch) by the Bird composers where the provider choice is
        explicit.
        """
        self.env['oduist.license'].check_license('connect', silent=False)
        channels = self._get_bird_sender_channels(outgoing_callerid)
        res = channel = False
        for channel in channels:
            res = self.client_send(recipient, channel, body)
            if res:
                break
        if not res:
            raise ValidationError(
                'Bird could not send the message. For WhatsApp check the '
                '24-hour customer service window (use a template to start '
                'a conversation) or check the Odoo log.')
        return self._register_bird_outgoing_message(
            res, channel, recipient, body, res_id, res_model)

    def send_bird_template(self, recipient, template, params=None, res_id=None,
                           res_model=None):
        """Send an approved template (the only way to start a WhatsApp
        conversation outside the 24-hour window).

        ``template`` is a connect.bird.message_template record or id,
        ``params`` a {key: value} dict for the template variables.
        """
        self.env['oduist.license'].check_license('connect', silent=False)
        if not isinstance(template, models.BaseModel):
            template = self.env['connect.bird.message_template'].browse(template)
        template.ensure_one()
        channel = self.env['connect.bird.channel'].get_default_channel(
            template.platform or 'whatsapp')
        user_channel = self.env.user.connect_user.bird_message_channel
        if user_channel and user_channel.platform_id == (template.platform or 'whatsapp'):
            channel = user_channel
        payload = {
            'receiver': {'contacts': [{'identifierValue': recipient}]},
            'template': {
                'projectId': template.project_id,
                'version': 'latest',
                'locale': template.locale or 'en',
                'parameters': [
                    {'type': 'string', 'key': key, 'value': str(value)}
                    for key, value in (params or {}).items()
                ],
            },
        }
        res = self.env['connect.settings'].bird_request(
            'POST', '/channels/{}/messages'.format(channel.sid), payload)
        body = template.body_preview or 'Template: {}'.format(template.name)
        return self._register_bird_outgoing_message(
            res, channel, recipient, body, res_id, res_model)

    def client_send(self, recipient, channel, body, media_url=None):
        """POST one message to the Bird Channels API; False on failure."""
        payload = {
            'receiver': {'contacts': [{'identifierValue': recipient}]},
        }
        if media_url:
            payload['body'] = {
                'type': 'image',
                'image': {
                    'images': [{'mediaUrl': media_url}],
                    'text': body or '',
                },
            }
        else:
            payload['body'] = {'type': 'text', 'text': {'text': body}}
        res = self.env['connect.settings'].bird_request(
            'POST', '/channels/{}/messages'.format(channel.sid), payload,
            raise_exc=False)
        if not res:
            logger.warning(
                'Bird send via %s channel %s to %s failed.',
                channel.platform_id, channel.identifier, recipient)
            return False
        logger.info('Bird message to %s is sent.', recipient)
        return res

    def _register_bird_outgoing_message(self, res, channel, recipient, body,
                                        res_id=None, res_model=None):
        """Create the ledger record and post to the target chatter."""
        sender_user = self.env.user
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        message = self.env['connect.message'].sudo().create({
            'bird_message_id': res.get('id'),
            'bird_channel': channel.id,
            'message_type': (
                'WhatsApp' if channel.platform_id == 'whatsapp' else 'sms'),
            'from_number': channel.identifier,
            'to_number': recipient,
            'body': body,
            'sender_user': sender_user.id,
            'partner': partner.id if partner else False,
            'res_id': res_id,
            'res_model': res_model,
            'status': self._map_bird_message_status(res.get('status', 'sent')),
        })
        # Add message to chatter
        if res_model and res_id:
            mt_note = self.env.ref('mail.mt_note').id
            obj = self.env[res_model].with_user(SUPERUSER_ID).browse(res_id)
            if hasattr(obj, 'message_post'):
                link = Markup(
                    '<small><a href="/web#id={}&model=connect.message&view_type=form">'
                    'Message</a></small>'.format(message.id))
                chat_body = Markup(str(Markup.escape(body)) + '<br/>' + str(link))
                kwargs = {
                    'body': chat_body,
                    'subtype_id': mt_note,
                    'message_type': message.message_type,
                    'author_id': sender_user.partner_id.id,
                }
                chatter = obj.with_context(
                    mail_create_nosubscribe=True).message_post(**kwargs)
                mail_notification_values = [{
                    'author_id': chatter.author_id.id,
                    'mail_message_id': chatter.id,
                    'res_partner_id': chatter.author_id.id,
                    'sms_number': channel.identifier,
                    'notification_type': message.message_type,
                    'is_read': True,
                    'notification_status': 'ready',
                }]
                self.env['mail.notification'].sudo().create(
                    mail_notification_values)
                self.env['connect.settings'].connect_reload_view(res_model)
        return message

    @api.model
    def _extract_bird_body(self, payload):
        """(text, media_url, media_content_type) from a Bird message body.

        All payload-shape assumptions are centralized here so live-traffic
        fixes touch one place.
        """
        body = payload.get('body') or {}
        body_type = body.get('type')
        if body_type == 'text':
            return (body.get('text') or {}).get('text', ''), None, None
        media_types = {
            'image': 'image/*',
            'file': 'application/octet-stream',
            'audio': 'audio/*',
            'video': 'video/*',
        }
        if body_type in media_types:
            section = body.get(body_type) or {}
            items = section.get('{}s'.format(body_type)) or section.get('files') or []
            media_url = items[0].get('mediaUrl') if items else None
            content_type = (items[0].get('contentType')
                            if items else None) or media_types[body_type]
            return section.get('text', ''), media_url, content_type
        logger.info('Unhandled Bird message body type: %s', body_type)
        return '', None, None

    @api.model
    def receive_bird(self, payload, event):
        """Create a ledger record from an inbound Bird message webhook."""
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return True
        try:
            bird_message_id = payload.get('id')
            if not bird_message_id:
                logger.warning('Bird inbound message without id, ignored.')
                return True
            # Bird retries webhooks for up to 8 hours: dedupe by message id.
            if self.sudo().search(
                    [('bird_message_id', '=', bird_message_id)], limit=1):
                return True
            logger.info('Received Bird %s webhook data:\n%s', event, payload)
            channel = self.env['connect.bird.channel'].sudo().search(
                [('sid', '=', payload.get('channelId'))], limit=1)
            sender = ((payload.get('sender') or {}).get('contact') or {})
            from_number = sender.get('identifierValue')
            to_number = channel.identifier or ''
            if not from_number:
                logger.warning('Bird inbound message without sender, ignored.')
                return True
            text, media_url, media_content_type = self._extract_bird_body(payload)
            values = {
                'bird_message_id': bird_message_id,
                'bird_channel': channel.id,
                'from_number': from_number,
                'to_number': to_number,
                'body': text,
                'status': 'received',
                'message_type': (
                    'WhatsApp' if event.startswith('whatsapp') else 'sms'),
            }
            if media_url:
                values.update({
                    'media_url': media_url,
                    'media_content_type': media_content_type,
                    'num_media': 1,
                })
            partner = self.env['res.partner'].get_partner_by_number(from_number)
            if partner:
                values.update({'partner': partner.id})
            # Thread into the latest conversation with this correspondent.
            last_message = self.env['connect.message'].sudo().search(
                [
                    ('from_number', '=', to_number),
                    ('to_number', '=', from_number),
                ],
                order='create_date desc', limit=1)
            target_msg = False
            valid_target = False
            if last_message and last_message.res_model and last_message.res_id:
                target_rec = self.env[last_message.res_model].sudo().browse(
                    last_message.res_id)
                if target_rec.exists():
                    values.update({
                        'res_model': last_message.res_model,
                        'res_id': last_message.res_id,
                        'parent_message': last_message.id,
                    })
                    target_msg = last_message
                    valid_target = True
                else:
                    logger.warning(
                        'Target record %s(%s) does not exist anymore',
                        last_message.res_model, last_message.res_id)
            message = self.env['connect.message'].sudo().create(values)
            # Message destination handling
            if not target_msg:
                target_msg = message
                valid_target = True
                config = self.env[
                    'connect.bird.message_configuration'
                ].sudo().search([('channel', '=', channel.id)], limit=1)
                dest_model = (
                    config.destination
                    if config and config.destination
                    else 'res.partner')
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
                            mail_create_nosubscribe=True
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
                    logger.warning('Destination model %s not found', dest_model)
            # Add message to chatter
            if (valid_target and target_msg and target_msg.res_model
                    and target_msg.res_id):
                obj = self.env[target_msg.res_model].with_user(
                    SUPERUSER_ID).browse(target_msg.res_id)
                if obj.exists() and hasattr(obj, 'message_post'):
                    body_html = Markup(
                        "<div class='d-flex flex-row px-1'>"
                        "<span class='px-1'>{}</span></div>").format(text)
                    if message.media_url:
                        body_html = Markup(
                            "<div class='d-flex flex-row'>"
                            "<span class='px-1'>{}</span>"
                            "<br/>{}</div>").format(
                                text, Markup(message.media_widget))
                    link = Markup(
                        '<small><a href="/web#id={}&model=connect.message&view_type=form">'
                        'Message</a></small>'.format(message.id))
                    body_html = Markup(str(body_html) + str(link))
                    mt_comment = self.env.ref('mail.mt_comment').id
                    kwargs = {
                        'body': body_html,
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
            logger.exception('Error handling incoming Bird message: %s', e)
        return True

    @api.model
    def update_bird_status(self, payload, event):
        """Apply a *.outbound status event; upsert unknown messages
        (sent from the Bird dashboard, or the webhook raced our commit).
        """
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return True
        try:
            bird_message_id = payload.get('id')
            if not bird_message_id:
                return True
            status = self._map_bird_message_status(payload.get('status'))
            message = self.env['connect.message'].sudo().search(
                [('bird_message_id', '=', bird_message_id)], limit=1)
            if not message:
                channel = self.env['connect.bird.channel'].sudo().search(
                    [('sid', '=', payload.get('channelId'))], limit=1)
                receiver_contacts = (
                    (payload.get('receiver') or {}).get('contacts') or [{}])
                to_number = receiver_contacts[0].get('identifierValue', '')
                text = self._extract_bird_body(payload)[0]
                message = self.env['connect.message'].sudo().create({
                    'bird_message_id': bird_message_id,
                    'bird_channel': channel.id,
                    'from_number': channel.identifier or '',
                    'to_number': to_number,
                    'body': text,
                    'status': status,
                    'message_type': (
                        'WhatsApp' if event.startswith('whatsapp') else 'sms'),
                })
            else:
                message.write({'status': status})
            if payload.get('status') in BIRD_FAILED_STATUSES:
                failure = (payload.get('failure')
                           or payload.get('error') or {})
                message.write({
                    'has_error': True,
                    'error_code': str(
                        failure.get('code', '') or ''),
                    'error_message': (
                        failure.get('description')
                        or failure.get('message') or payload.get('status')),
                })
        except Exception as e:
            logger.exception('Error handling Bird message status: %s', e)
        return True

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
