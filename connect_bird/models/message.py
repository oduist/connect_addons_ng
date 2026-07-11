# -*- coding: utf-8 -*-
import ast
import logging

from markupsafe import Markup

from odoo import models, fields, api, SUPERUSER_ID
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Normalize Bird message statuses to the core display vocabulary. Statuses
# not listed here are stored as-is (sent, delivered, ...).
BIRD_MESSAGE_STATUS_MAP = {
    'accepted': 'sent',
    'processing': 'sent',
    'undelivered': 'failed',
    'rejected': 'failed',
    'expired': 'failed',
}
BIRD_FAILED_STATUSES = ('undelivered', 'failed', 'rejected', 'expired')


class ConnectMessage(models.Model):
    _inherit = 'connect.message'

    bird_message_id = fields.Char('Bird Message ID', index=True, readonly=True)
    bird_number = fields.Many2one(
        'connect.bird.number', ondelete='set null', readonly=True)

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        """Override: also check Bird sender numbers for direction."""
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                our_numbers = set(
                    self.env['connect.bird.number'].search([]).mapped('number'))
                if rec.from_number in our_numbers:
                    rec.direction = 'outgoing'
                else:
                    super(ConnectMessage, rec)._compute_direction()

    @api.model
    def _map_bird_message_status(self, status):
        return BIRD_MESSAGE_STATUS_MAP.get(status, status)

    @api.model
    def _normalize_bird_status(self, status):
        """The platform returns the message status either as a plain
        string or as an object; flatten defensively.
        """
        if isinstance(status, dict):
            status = (status.get('value') or status.get('state')
                      or status.get('status') or '')
        return self._map_bird_message_status(status or 'sent')

    @api.model
    def _get_bird_sender_numbers(self, outgoing_callerid=None):
        """Ordered (product, number) send attempts: an explicit sender
        disables number fallback; automatic selection tries WhatsApp
        first, then SMS (mirrors the Twilio behavior).
        """
        Number = self.env['connect.bird.number']
        if outgoing_callerid:
            if isinstance(outgoing_callerid, models.BaseModel):
                number = outgoing_callerid
            else:
                number = Number.search([
                    '|', ('number', '=', outgoing_callerid),
                    ('sid', '=', outgoing_callerid),
                ], limit=1)
            if not number:
                raise ValidationError(
                    'No Bird number matches sender {}!'.format(
                        outgoing_callerid))
            numbers = [number]
        elif self.env.user.connect_user.bird_message_number:
            numbers = [self.env.user.connect_user.bird_message_number]
        else:
            numbers = []
            for capability in ('whatsapp', 'sms'):
                try:
                    number = Number.get_default_number(capability)
                except ValidationError:
                    continue
                if number not in numbers:
                    numbers.append(number)
            if not numbers:
                raise ValidationError(
                    'No active Bird number. Run Sync in Bird Settings '
                    'and check your numbers!')
        attempts = []
        for number in numbers:
            if number.has_capability('whatsapp'):
                attempts.append(('whatsapp', number))
            if number.has_capability('sms'):
                attempts.append(('sms', number))
        if not attempts:
            raise ValidationError(
                'The selected Bird number has no messaging capability!')
        return attempts

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
        attempts = self._get_bird_sender_numbers(outgoing_callerid)
        res = product = number = False
        for product, number in attempts:
            res = self.client_send(recipient, number, body, product)
            if res:
                break
        if not res:
            raise ValidationError(
                'Bird could not send the message. For WhatsApp check the '
                '24-hour customer service window (use a template to start '
                'a conversation) or check the Odoo log.')
        return self._register_bird_outgoing_message(
            res, number, product, recipient, body, res_id, res_model)

    def send_bird_template(self, recipient, template, params=None,
                           res_id=None, res_model=None):
        """Send an approved WhatsApp template (the only way to start a
        conversation outside the 24-hour window).

        ``template`` is a connect.bird.message_template record or id,
        ``params`` a {key: value} dict for the template variables. The
        request shape is confirmed against the live platform
        (POST /v1/whatsapp/messages is present but not yet publicly
        documented).
        """
        self.env['oduist.license'].check_license('connect', silent=False)
        if not isinstance(template, models.BaseModel):
            template = self.env['connect.bird.message_template'].browse(template)
        template.ensure_one()
        number = self.env.user.connect_user.bird_message_number
        if not number or not number.has_capability('whatsapp'):
            number = self.env['connect.bird.number'].get_default_number(
                'whatsapp')
        payload = {
            'to': recipient,
            'from': number.number,
            'template': {
                'name': template.name,
                'locale': template.locale or 'en',
                'variables': {
                    str(key): str(value)
                    for key, value in (params or {}).items()
                },
            },
        }
        res = self.env['connect.settings'].bird_request(
            'POST', '/whatsapp/messages', payload)
        body = template.body_preview or 'Template: {}'.format(template.name)
        return self._register_bird_outgoing_message(
            res, number, 'whatsapp', recipient, body, res_id, res_model)

    def client_send(self, recipient, number, body, product):
        """POST one message to the Bird platform; False on failure."""
        settings = self.env['connect.settings']
        if product == 'sms':
            payload = {
                'to': recipient,
                'from': number.number,
                'text': body,
                'category': settings.sudo().get_param(
                    'bird_sms_category') or 'transactional',
            }
            path = '/sms/messages'
        else:
            # WhatsApp free-form text inside the 24h customer-service
            # window; shape confirmed against the live platform.
            payload = {
                'to': recipient,
                'from': number.number,
                'text': body,
            }
            path = '/whatsapp/messages'
        res = settings.bird_request('POST', path, payload, raise_exc=False)
        if not res:
            logger.warning(
                'Bird %s send from %s to %s failed.',
                product, number.number, recipient)
            return False
        logger.info('Bird %s message to %s is sent.', product, recipient)
        return res

    def _register_bird_outgoing_message(self, res, number, product,
                                        recipient, body, res_id=None,
                                        res_model=None):
        """Create the ledger record and post to the target chatter."""
        sender_user = self.env.user
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        message = self.env['connect.message'].sudo().create({
            'bird_message_id': res.get('id'),
            'bird_number': number.id,
            'message_type': 'WhatsApp' if product == 'whatsapp' else 'sms',
            'from_number': number.number,
            'to_number': recipient,
            'body': body,
            'sender_user': sender_user.id,
            'partner': partner.id if partner else False,
            'res_id': res_id,
            'res_model': res_model,
            'status': self._normalize_bird_status(res.get('status')),
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
                    'sms_number': number.number,
                    'notification_type': message.message_type,
                    'is_read': True,
                    'notification_status': 'ready',
                }]
                self.env['mail.notification'].sudo().create(
                    mail_notification_values)
                self.env['connect.settings'].connect_reload_view(res_model)
        return message

    @api.model
    def _extract_bird_message_data(self, data):
        """(message_id, from_number, to_number, text, media_url,
        media_content_type) from a webhook event ``data`` object.

        All payload-shape assumptions are centralized here so live-traffic
        fixes touch one place. Known keys from the published SMS events:
        sms_id, to, from, carrier, error; inbound events additionally
        carry the text body.
        """
        message_id = (data.get('sms_id') or data.get('whatsapp_id')
                      or data.get('message_id') or data.get('id'))
        from_number = data.get('from')
        to_number = data.get('to')
        text = data.get('text') or data.get('body') or ''
        media = data.get('media') or []
        media_url = None
        media_content_type = None
        if isinstance(media, list) and media:
            first = media[0] if isinstance(media[0], dict) else {}
            media_url = first.get('url')
            media_content_type = first.get('content_type')
        return (message_id, from_number, to_number, text,
                media_url, media_content_type)

    @api.model
    def receive_bird(self, data, event_type):
        """Create a ledger record from an inbound Bird message event."""
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return True
        try:
            (bird_message_id, from_number, to_number, text,
             media_url, media_content_type) = \
                self._extract_bird_message_data(data)
            if not bird_message_id:
                logger.warning('Bird inbound message without id, ignored.')
                return True
            # Bird retries webhooks: dedupe by message id.
            if self.sudo().search(
                    [('bird_message_id', '=', bird_message_id)], limit=1):
                return True
            logger.info('Received Bird %s event data:\n%s', event_type, data)
            if not from_number:
                logger.warning('Bird inbound message without sender, ignored.')
                return True
            number = self.env['connect.bird.number'].sudo().search(
                [('number', '=', to_number)], limit=1)
            values = {
                'bird_message_id': bird_message_id,
                'bird_number': number.id,
                'from_number': from_number,
                'to_number': to_number or '',
                'body': text,
                'status': 'received',
                'message_type': (
                    'WhatsApp' if event_type.startswith('whatsapp')
                    else 'sms'),
            }
            if media_url:
                values.update({
                    'media_url': media_url,
                    'media_content_type': media_content_type or '',
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
                ].sudo().search([('number', '=', number.id)], limit=1)
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
    def update_bird_status(self, data, event_type):
        """Apply a message lifecycle event (sms.sent, sms.delivered,
        sms.failed, ...): the status is carried by the event name itself.
        Unknown message ids are upserted (sent outside Odoo, or the
        webhook raced our send commit).
        """
        if not self.env['oduist.license'].check_license('connect', silent=True):
            return True
        try:
            (bird_message_id, from_number, to_number, text,
             _media_url, _media_content_type) = \
                self._extract_bird_message_data(data)
            if not bird_message_id:
                return True
            raw_status = event_type.split('.')[-1]
            status = self._map_bird_message_status(raw_status)
            message = self.env['connect.message'].sudo().search(
                [('bird_message_id', '=', bird_message_id)], limit=1)
            if not message:
                number = self.env['connect.bird.number'].sudo().search(
                    [('number', '=', from_number)], limit=1)
                message = self.env['connect.message'].sudo().create({
                    'bird_message_id': bird_message_id,
                    'bird_number': number.id,
                    'from_number': from_number or '',
                    'to_number': to_number or '',
                    'body': text,
                    'status': status,
                    'message_type': (
                        'WhatsApp' if event_type.startswith('whatsapp')
                        else 'sms'),
                })
            else:
                message.write({'status': status})
            if raw_status in BIRD_FAILED_STATUSES:
                error = data.get('error') or {}
                message.write({
                    'has_error': True,
                    'error_code': str(error.get('code', '') or ''),
                    'error_message': (
                        error.get('description') or error.get('message')
                        or raw_status),
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
