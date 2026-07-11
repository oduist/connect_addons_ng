# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import models, fields, api
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

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


class InfobipWhatsappTemplate(models.Model):
    """WhatsApp message templates (Meta approval flow via Infobip).

    Mirrors the Twilio/Telnyx template shape (ADR-033). Unlike Telnyx,
    Infobip scopes templates per sender: the API path embeds the sender
    number, so sender_id is required (ADR-035).
    """
    _name = 'connect.infobip.whatsapp_template'
    _description = 'Infobip WhatsApp Template'
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(required=True, help='Template name (lowercase, digits and underscores).')
    language = fields.Char(required=True, default='en',
        help='Template language code, e.g. en, en_US, es.')
    category = fields.Selection(selection=WHATSAPP_CATEGORIES, required=True, default='UTILITY')
    sender_id = fields.Many2one(
        'connect.infobip.whatsapp_sender', string='Sender', required=True,
        ondelete='cascade')
    body = fields.Text(string='Body',
        help='Template body. Use {{1}}, {{2}}, ... for variables.')
    variables = fields.Text(string='Variables',
        help='JSON mapping like {"1": "Sample value"} used as the preview/default values.')
    structure = fields.Text(string='Structure (JSON)', readonly=True,
        help='Raw template structure as returned by Infobip.')
    infobip_id = fields.Char(string='Infobip ID', readonly=True, index=True)
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

    def _as_message_content(self, variables=None):
        """Build the /whatsapp/1/message/template content payload."""
        self.ensure_one()
        values = [str(v) for v in (variables or [])]
        return {
            'templateName': self.name,
            'templateData': {'body': {'placeholders': values}},
            'language': self.language,
        }

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

    def create_in_infobip(self):
        """Submit the template for Meta approval via Infobip."""
        self.ensure_one()
        if self.infobip_id:
            raise ValidationError('This template is already submitted!')
        if not self.body:
            raise ValidationError('Template body is required!')
        if not self.sender_id:
            raise ValidationError('Select the WhatsApp sender first!')
        structure = {'body': {'text': self.body}}
        sample_values = self._ordered_variable_values(self.variables)
        if sample_values:
            structure['body']['examples'] = sample_values
        payload = {
            'name': self.name,
            'language': self.language,
            'category': self.category,
            'structure': structure,
        }
        try:
            response = self.env['connect.settings'].infobip_api_request(
                'POST', '/whatsapp/2/senders/{}/templates'.format(
                    self.sender_id.number.lstrip('+')),
                payload)
        except Exception as e:
            raise ValidationError('Template submit error: {}'.format(e))
        self.write({
            'infobip_id': response.get('id') or False,
            'status': response.get('status') or 'PENDING',
            'structure': json.dumps(response.get('structure') or structure,
                                    default=str),
        })
        self.env['connect.settings'].connect_notify(
            'Template {} submitted for approval'.format(self.name))
        return True

    @api.model
    def sync(self):
        """Pull templates of every synced sender (templates are per-sender
        at Infobip)."""
        Settings = self.env['connect.settings']
        senders = self.env['connect.infobip.whatsapp_sender'].search([])
        seen_ids = set()
        for sender in senders:
            try:
                response = Settings.infobip_api_request(
                    'GET', '/whatsapp/2/senders/{}/templates'.format(
                        sender.number.lstrip('+')))
            except Exception as e:
                logger.warning(
                    'WhatsApp templates sync failed for sender %s: %s',
                    sender.number, e)
                continue
            items = response.get('templates') or response.get('results') or []
            for item in items:
                template_id = item.get('id')
                if not template_id:
                    continue
                seen_ids.add(template_id)
                structure = item.get('structure') or {}
                status = item.get('status') or 'PENDING'
                if status not in dict(WHATSAPP_STATUSES):
                    status = 'PENDING'
                vals = {
                    'infobip_id': template_id,
                    'name': item.get('name'),
                    'language': item.get('language'),
                    'category': item.get('category') or 'UTILITY',
                    'status': status,
                    'rejection_reason': item.get('rejectionReason') or False,
                    'structure': json.dumps(structure, default=str),
                    'sender_id': sender.id,
                }
                body = (structure.get('body') or {}).get('text')
                if body:
                    vals['body'] = body
                rec = self.search([('infobip_id', '=', template_id)], limit=1)
                if not rec:
                    rec = self.search([
                        ('infobip_id', '=', False),
                        ('name', '=', vals['name']),
                        ('language', '=', vals['language']),
                        ('sender_id', '=', sender.id)], limit=1)
                if rec:
                    rec.write(vals)
                    debug(self, 'Updated WhatsApp template {}'.format(rec.name))
                else:
                    self.create([vals])
                    debug(self, 'Created WhatsApp template {}'.format(vals['name']))
        # Drop local copies of templates removed in Infobip (submitted ones only)
        missing = self.search([
            ('infobip_id', '!=', False),
            ('infobip_id', 'not in', list(seen_ids))])
        if missing:
            debug(self, 'Removing missing WhatsApp templates: {}'.format(
                ', '.join(missing.mapped('name'))))
            missing.unlink()

    def action_sync(self):
        self.sync()
        return True
