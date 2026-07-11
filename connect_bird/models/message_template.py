# -*- coding: utf-8 -*-
import json
import logging

from odoo import fields, models, api

logger = logging.getLogger(__name__)


class BirdMessageTemplate(models.Model):
    """Approved message templates synced read-only from the Bird
    Touchpoints API. Required to start a WhatsApp conversation outside the
    24-hour customer-service window; templates are authored and approved
    in the Bird dashboard.
    """
    _name = 'connect.bird.message_template'
    _description = 'Bird Message Template'
    _rec_name = 'name'
    _order = 'name, locale'

    sid = fields.Char('Template ID', required=True, index=True, readonly=True)
    project_id = fields.Char('Project ID', required=True, readonly=True)
    name = fields.Char(required=True, readonly=True)
    locale = fields.Char('Locale', readonly=True)
    status = fields.Char(readonly=True)
    platform = fields.Char(readonly=True, help='Target platform, e.g. whatsapp.')
    whatsapp_template_name = fields.Char(
        readonly=True, help='Template name registered with Meta.')
    variables = fields.Text(
        readonly=True,
        help='JSON list of template variables: [{"key", "type", "description"}].')
    body_preview = fields.Text(readonly=True)

    def get_variable_keys(self):
        self.ensure_one()
        try:
            return [v.get('key') for v in json.loads(self.variables or '[]')
                    if isinstance(v, dict) and v.get('key')]
        except ValueError:
            return []

    @api.model
    def _extract_body_preview(self, item):
        """Best-effort text preview from genericContent blocks."""
        try:
            for content in item.get('genericContent') or []:
                for block in content.get('blocks') or []:
                    block_type = block.get('type')
                    block_body = block.get(block_type) or {}
                    text = block_body.get('text')
                    if text:
                        return text
        except Exception:
            pass
        return ''

    @api.model
    def _iter_remote_templates(self):
        """Yield channel-template objects across all workspace projects."""
        settings = self.env['connect.settings']
        page_token = None
        projects = []
        while True:
            params = {'limit': 100}
            if page_token:
                params['pageToken'] = page_token
            data = settings.bird_request(
                'GET', '/projects', params=params, raise_exc=False)
            if data is False:
                logger.warning('Bird projects listing failed, template sync skipped.')
                return
            projects.extend(data.get('results', data.get('projects', [])) or [])
            page_token = data.get('nextPageToken')
            if not page_token:
                break
        for project in projects:
            project_id = project.get('id')
            if not project_id:
                continue
            page_token = None
            while True:
                params = {'limit': 100}
                if page_token:
                    params['pageToken'] = page_token
                data = settings.bird_request(
                    'GET', '/projects/{}/channel-templates'.format(project_id),
                    params=params, raise_exc=False)
                if data is False:
                    break
                for item in data.get('results', data.get('channelTemplates', [])) or []:
                    yield project, item
                page_token = data.get('nextPageToken')
                if not page_token:
                    break

    @api.model
    def sync(self):
        """Upsert active templates, drop vanished ones."""
        remote_sids = []
        for project, item in self._iter_remote_templates():
            sid = item.get('id')
            if not sid:
                continue
            platforms = [str(p).lower() for p in item.get('supportedPlatforms') or []]
            deployments = item.get('deployments') or {}
            if isinstance(deployments, list):
                deployments = next(
                    (d for d in deployments if isinstance(d, dict)), {})
            values = {
                'sid': sid,
                'project_id': item.get('projectId') or project.get('id'),
                'name': item.get('name') or project.get('name') or sid,
                'locale': item.get('defaultLocale'),
                'status': item.get('status'),
                'platform': platforms[0] if platforms else '',
                'whatsapp_template_name': deployments.get('whatsappTemplateName'),
                'variables': json.dumps(item.get('variables') or []),
                'body_preview': self._extract_body_preview(item),
            }
            remote_sids.append(sid)
            template = self.search([('sid', '=', sid)], limit=1)
            if template:
                template.write(values)
            else:
                self.create(values)
        stale = self.search([('sid', 'not in', remote_sids)])
        if stale:
            stale.unlink()
        return True
