# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

logger = logging.getLogger(__name__)

WHATSAPP_CATEGORIES = [
    ('MARKETING', 'Marketing'),
    ('UTILITY', 'Utility'),
    ('AUTHENTICATION', 'Authentication'),
]

WHATSAPP_STATUSES = [
    ('unsubmitted', 'Unsubmitted'),
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
    ('PAUSED', 'Paused'),
    ('DISABLED', 'Disabled'),
]


class TelnyxWhatsappTemplate(models.Model):
    """WhatsApp message templates (Meta approval flow via Telnyx).

    Mirrors the Twilio connect.message_content_template shape (ADR-033).
    """
    _name = 'connect.telnyx.whatsapp_template'
    _description = 'Telnyx WhatsApp Template'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(required=True, help='Template name (lowercase, digits and underscores).')
    language = fields.Char(required=True, default='en',
        help='Template language code, e.g. en, en_US, es.')
    category = fields.Selection(selection=WHATSAPP_CATEGORIES, required=True, default='UTILITY')
    body = fields.Text(string='Body',
        help='Template body. Use {{1}}, {{2}}, ... for variables.')
    variables = fields.Text(string='Variables',
        help='JSON mapping like {"1": "Sample value"} used as the preview/default values.')
    components = fields.Text(string='Components (JSON)', readonly=True,
        help='Raw template components as returned by Telnyx.')
    waba_id = fields.Char(string='Business Account ID')
    telnyx_id = fields.Char(string='Telnyx ID', readonly=True, index=True)
    template_id = fields.Char(string='Meta Template ID', readonly=True)
    status = fields.Selection(selection=WHATSAPP_STATUSES, default='unsubmitted', required=True, readonly=True)
    rejection_reason = fields.Char(readonly=True)
    display_status = fields.Html(compute='_compute_display_status', sanitize=False)

    @api.constrains('variables')
    def _check_variables_json(self):
        for rec in self:
            if not rec.variables:
                continue
            try:
                dict(json.loads(rec.variables))
            except Exception as e:
                raise ValidationError(
                    'Variables must be a JSON object like {"1": "value"}.') from e

    @api.constrains('name')
    def _check_name(self):
        for rec in self:
            if rec.name and not re.match(r'^[a-z0-9_]+$', rec.name):
                raise ValidationError(
                    'Template name must contain only lowercase letters, digits and underscores.')

    def _compute_display_status(self):
        colors = {
            'APPROVED': 'green',
            'REJECTED': 'red',
            'PAUSED': 'orange',
            'DISABLED': 'red',
            'PENDING': 'orange',
            'unsubmitted': 'gray',
        }
        for rec in self:
            color = colors.get(rec.status, 'gray')
            rec.display_status = '<span style="color: {}">{}</span>'.format(
                color, rec.status)

    def _as_message_template(self, variables=None):
        """Build the messages.send_whatsapp template payload."""
        self.ensure_one()
        template = {
            'name': self.name,
            'language': {'code': self.language},
        }
        values = list(variables) if variables else []
        if values:
            template['components'] = [{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': str(v)} for v in values
                ],
            }]
        return template

    def _ordered_variable_values(self, variables_json):
        """Return body parameter values ordered by the {{n}} index."""
        self.ensure_one()
        try:
            mapping = json.loads(variables_json) if variables_json else {}
        except Exception:
            mapping = {}
        indices = []
        for idx in re.findall(r"{{\s*(\d+)\s*}}", self.body or ''):
            if idx not in indices:
                indices.append(idx)
        return [mapping.get(idx, '') for idx in indices]

    def create_in_telnyx(self):
        """Submit the template for Meta approval via Telnyx."""
        self.ensure_one()
        if self.telnyx_id:
            raise ValidationError('This template is already submitted!')
        if not self.body:
            raise ValidationError('Template body is required!')
        waba_id = self.waba_id
        if not waba_id:
            sender = self.env['connect.telnyx.whatsapp_sender'].search(
                [('waba_id', '!=', False)], limit=1)
            waba_id = sender.waba_id
        if not waba_id:
            raise ValidationError(
                'No WhatsApp Business Account found. Sync WhatsApp senders first '
                'or set the Business Account ID on the template.')
        client = self.env['connect.settings'].get_telnyx_client()
        components = [{'type': 'BODY', 'text': self.body}]
        sample_values = self._ordered_variable_values(self.variables)
        if sample_values:
            components[0]['example'] = {'body_text': [sample_values]}
        try:
            response = client.whatsapp.templates.create(
                name=self.name,
                language=self.language,
                category=self.category,
                waba_id=waba_id,
                components=components,
            )
        except Exception as e:
            raise ValidationError('Template submit error: {}'.format(
                format_connect_response(e)))
        data = getattr(response, 'data', None) or response
        self.write({
            'telnyx_id': getattr(data, 'id', False),
            'template_id': getattr(data, 'template_id', False),
            'status': getattr(data, 'status', None) or 'PENDING',
            'waba_id': waba_id,
        })
        self.env['connect.settings'].connect_notify(
            'Template {} submitted for approval'.format(self.name))
        return True

    @api.model
    def _template_body_from_components(self, components):
        for component in components or []:
            if (component.get('type') or '').upper() == 'BODY':
                return component.get('text')
        return False

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_telnyx_client()
        try:
            items = list(client.whatsapp.templates.list())
        except Exception as e:
            raise ValidationError("Failed to sync WhatsApp Templates: {}".format(
                format_connect_response(e)))
        seen_ids = set()
        for item in items:
            if not item.id:
                continue
            seen_ids.add(item.id)
            components = [
                c if isinstance(c, dict) else dict(c)
                for c in (item.components or [])
            ]
            waba = item.whatsapp_business_account
            vals = {
                'telnyx_id': item.id,
                'template_id': item.template_id,
                'name': item.name,
                'language': item.language,
                'category': item.category,
                'status': item.status or 'PENDING',
                'rejection_reason': item.rejection_reason,
                'components': json.dumps(components, default=str),
                'waba_id': waba.id if waba else False,
            }
            body = self._template_body_from_components(components)
            if body:
                vals['body'] = body
            rec = self.search([('telnyx_id', '=', item.id)], limit=1)
            if not rec:
                rec = self.search([
                    ('telnyx_id', '=', False),
                    ('name', '=', item.name),
                    ('language', '=', item.language)], limit=1)
            if rec:
                rec.write(vals)
                debug(self, 'Updated WhatsApp template {}'.format(rec.name))
            else:
                self.create([vals])
                debug(self, 'Created WhatsApp template {}'.format(vals['name']))
        # Drop local copies of templates removed in Telnyx (submitted ones only)
        missing = self.search([
            ('telnyx_id', '!=', False),
            ('telnyx_id', 'not in', list(seen_ids))])
        if missing:
            debug(self, 'Removing missing WhatsApp templates: {}'.format(
                ', '.join(missing.mapped('name'))))
            missing.unlink()

    def action_sync(self):
        self.sync()
        return True
