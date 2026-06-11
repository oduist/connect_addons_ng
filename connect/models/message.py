import ast
import logging

import phonenumbers
from markupsafe import Markup, escape
from phonenumbers import parse, format_number, PhoneNumberFormat

from odoo import models, fields, api, SUPERUSER_ID, release
from odoo.exceptions import ValidationError
from odoo.tools import mail

logger = logging.getLogger(__name__)

mail.safe_attrs = mail.safe_attrs | frozenset(['controls'])


class ConnectMessage(models.Model):
    _name = 'connect.message'
    _description = 'Message'
    _order = 'create_date DESC'

    name = fields.Char(string='Name', compute='_compute_name')
    message_sid = fields.Char('Message SID')
    from_number = fields.Char('From', required=True)
    to_number = fields.Char('To', required=True)
    body = fields.Text('Message Body')
    num_media = fields.Integer('Number of Media Items', default=0)
    message_type = fields.Char(readonly=True)
    status = fields.Char(readonly=True, default='draft')
    direction = fields.Selection([
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
    ], compute='_compute_direction', store=True, readonly=True)
    direction_display = fields.Html(compute='_compute_direction_display', sanitize=False)
    status_display = fields.Html(compute='_compute_status_display', sanitize=False)
    sender_user = fields.Many2one('res.users', string='Sender User', ondelete='set null', readonly=True)
    sender_user_img = fields.Binary(related='sender_user.image_1920')
    partner = fields.Many2one('res.partner', ondelete='set null')
    partner_img = fields.Binary(related='partner.image_1920', string='Partner Image')
    from_city = fields.Char('From City')
    from_state = fields.Char('From State')
    from_zip = fields.Char('From ZIP')
    from_country = fields.Char('From Country')
    has_error = fields.Boolean(index=True)
    error_code = fields.Char()
    error_message = fields.Char()
    res_model = fields.Char()
    res_id = fields.Integer()
    ref = fields.Reference(selection='_reference_models', string="Reference", compute='_compute_ref', store=True)
    parent_message = fields.Many2one('connect.message', string='In Reply To', readonly=True)
    media_url = fields.Char()
    media_content_type = fields.Char()
    if release.version_info[0] >= 17.0:
        media_widget = fields.Html(compute='_get_media_widget', string='Media', sanitize=False)
    else:
        media_widget = fields.Char(compute='_get_media_widget', string='Media')

    def _get_media_widget(self):
        for rec in self:
            html = ''
            # media_url / media_content_type come from inbound webhook
            # params (MediaUrl0, MediaContentType0); escape both before
            # they land in this sanitize=False Html field (stored XSS).
            raw_url = rec.media_url or ''
            ctype = (rec.media_content_type or '').lower()
            url = escape(raw_url)
            if raw_url:
                if ctype.startswith('image/'):
                    html = '<img src="{}" style="max-width:50%;height:auto;"/>'.format(url)
                elif ctype.startswith('audio/'):
                    html = '<audio preload="auto" controls="controls"><source src="{}" type="{}"/></audio>'.format(url, escape(ctype or 'audio/mpeg'))
                elif ctype.startswith('video/'):
                    html = '<video controls style="max-width:50%"><source src="{}" type="{}"/></video>'.format(url, escape(ctype or 'video/mp4'))
                else:
                    html = '<a href="{}" target="_blank" rel="noopener">Download media</a>'.format(url)
            rec.media_widget = html

    @api.model
    def _reference_models(self):
        return [(model.model, model.name) for model in self.env['ir.model'].sudo().search([])]

    @api.depends('res_model', 'res_id')
    def _compute_ref(self):
        for rec in self:
            if rec.res_model and rec.res_id:
                try:
                    rec.ref = self.env[rec.res_model].browse(rec.res_id)
                except Exception:
                    rec.ref = False
            else:
                rec.ref = False

    @api.depends('status', 'sender_user')
    def _compute_direction(self):
        for rec in self:
            if rec.sender_user:
                rec.direction = 'outgoing'
            elif rec.status == 'received':
                rec.direction = 'incoming'
            else:
                rec.direction = 'incoming'

    @api.depends('direction')
    def _compute_direction_display(self):
        for rec in self:
            if rec.direction == 'incoming':
                rec.direction_display = '<span class="fa fa-arrow-down p-1"/>'
            elif rec.direction == 'outgoing':
                rec.direction_display = '<span class="fa fa-arrow-up p-1"/>'
            else:
                rec.direction_display = ''

    @api.depends('status')
    def _compute_status_display(self):
        for rec in self:
            s = (rec.status or '').lower()
            icon = ''
            if s in ('sent', 'sending'):
                icon = 'paper-plane'
            elif s in ('delivered', 'read', 'received'):
                icon = 'check-circle'
            elif s in ('queued', 'deferred'):
                icon = 'clock-o'
            elif s in ('failed', 'undeliverable', 'error'):
                icon = 'times-circle'
            elif s in ('draft',):
                icon = 'pencil-square-o'
            rec.status_display = f'<span class="fa fa-{icon}"/>' if icon else ''

    @staticmethod
    def _format_phone_number(number):
        try:
            if number:
                parsed_number = parse(number, None)
                return format_number(parsed_number, PhoneNumberFormat.INTERNATIONAL)
        except phonenumbers.phonenumberutil.NumberParseException:
            return number
        return number

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:
            if not record.message_type:
                record.message_type = 'mms' if record.num_media > 0 else 'sms'
        return res

    @api.depends('from_number', 'create_date', 'message_type')
    def _compute_name(self):
        for record in self:
            if record.create_date:
                formatted_number = self._format_phone_number(record.from_number)
                record.name = f"{record.message_type} from {formatted_number} on {record.create_date.strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                record.name = f"New {record.message_type}"

    def get_receive_message_values(self, params):
        return {
            'message_sid': params.get('MessageSid'),
            'from_number': params.get('From'),
            'to_number': params.get('To'),
            'body': params.get('Body'),
            'num_media': int(params.get('NumMedia', 0)),
            'from_city': params.get('FromCity'),
            'from_state': params.get('FromState'),
            'from_zip': params.get('FromZip'),
            'from_country': params.get('FromCountry'),
            'status': params.get('SmsStatus'),
            'media_content_type': params.get('MediaContentType0'),
            'media_url': params.get('MediaUrl0'),
        }

    def action_retry(self):
        for rec in self:
            if rec.status != 'failed':
                continue
            logger.warning('action_retry: send() not implemented in core module. Integration module should override.')
        return True
