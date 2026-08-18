# -*- coding: utf-8 -*-
import datetime
import jinja2
import logging
import random
import time
from urllib.parse import urljoin
from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.settings import debug

from .texml_response import pretty_xml

logger = logging.getLogger(__name__)


class TeXMLApp(models.Model):
    _name = 'connect.telnyx.texml'
    _description = 'TeXML app'
    _order = 'name'

    sid = fields.Char('SID', readonly=True)
    name = fields.Char(required=True)
    description = fields.Text()
    code_type = fields.Selection([
        ('texml', 'TeXML'),
        ('texpy', 'TeXPy'),
        ('model_method', 'model.method')
    ], help='Type of the language. To call mymodel.render() set mymodel.render as model.method',
        required=True, default='texml')
    texml = fields.Text(required=True, string='TeXML',
        default=pretty_xml('<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello</Say></Response>'))
    texpy = fields.Text('TeXPy')
    model = fields.Char()
    method = fields.Char()
    voice_url = fields.Char(compute='_get_telnyx_urls', compute_sudo=True)
    voice_fallback_url = fields.Char(compute='_get_telnyx_urls', compute_sudo=True)
    voice_status_url = fields.Char(compute='_get_telnyx_urls', compute_sudo=True)
    exten = fields.Many2one('connect.telnyx.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number')

    def _texml_app_params(self):
        self.ensure_one()
        params = {
            'friendly_name': self.name,
            'voice_url': self.voice_url,
            'voice_fallback_url': self.voice_fallback_url or '',
            'voice_method': 'post',
            'status_callback': self.voice_status_url,
            'status_callback_method': 'post',
        }
        # Without an outbound voice profile Telnyx rejects every call this
        # application places towards the PSTN.
        profile_id = self.env[
            'connect.settings']._ensure_telnyx_outbound_voice_profile()
        if profile_id:
            params['outbound'] = {'outbound_voice_profile_id': profile_id}
        return params

    def _find_telnyx_app_by_name(self, client):
        """Return the remote TeXML app matching this record's friendly_name."""
        self.ensure_one()
        for app in client.texml_applications.list():
            if getattr(app, 'friendly_name', None) == self.name:
                return app
        return None

    def create_telnyx_app(self, client):
        self.ensure_one()
        try:
            application = client.texml_applications.create(
                **self._texml_app_params())
        except Exception as e:
            # A TeXML app with this friendly_name may already exist on the
            # account (e.g. created by a previous database syncing the same
            # Telnyx account). Adopt it and update it to point at this env
            # instead of aborting the whole sync.
            if 'already in use' not in str(e) and '10015' not in str(e):
                raise
            existing = self._find_telnyx_app_by_name(client)
            if not existing:
                raise
            self.write({'sid': existing.id})
            debug(self, 'Adopted existing TeXML app {} ({}).'.format(
                self.name, existing.id))
            return self.update_telnyx_app(client)
        self.write({'sid': application.data.id})
        debug(self, 'Created TeXML app {} in Telnyx.'.format(self.name))
        return application.data

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('install_mode') == True:
            return super().create(vals_list)
        client = self.env['connect.settings'].get_telnyx_client()
        records = super().create(vals_list)
        for rec in records:
            rec.create_telnyx_app(client)
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env["connect.settings"].get_param("telnyx_auto_sync"):
            return res
        if self.env.context.get('skip_telnyx_sync'):
            return res
        client = self.env['connect.settings'].get_telnyx_client()
        for rec in self:
            if rec.sid:
                rec.update_telnyx_app(client)
        return res

    def update_telnyx_app(self, client):
        self.ensure_one()
        if self.sid:
            try:
                application = client.texml_applications.update(
                    self.sid, **self._texml_app_params())
                debug(self, 'TeXML app {} updated.'.format(self.name))
                return application.data
            except Exception as e:
                if 'not found' in str(e).lower() or '404' in str(e):
                    debug(self, 'TeXML app {} not found by sid {}, creating new app.'.format(
                        self.name, self.sid))
                    return self.create_telnyx_app(client)
                else:
                    raise
        else:
            debug(self, 'No current SID for TeXML app {}, creating new app.'.format(self.name))
            return self.create_telnyx_app(client)

    def unlink(self):
        if not self.env["connect.settings"].get_param("telnyx_auto_sync"):
            return super().unlink()
        client = self.env['connect.settings'].get_telnyx_client()
        for rec in self:
            if rec.sid:
                try:
                    client.texml_applications.delete(rec.sid)
                except Exception as e:
                    if 'not found' in str(e).lower() or '404' in str(e):
                        logger.warning('Cannot delete app %s in Telnyx, not found', rec.name)
                    else:
                        raise
        return super().unlink()

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_telnyx_client()
        for rec in self.search([]):
            rec.update_telnyx_app(client)

    def _get_telnyx_urls(self):
        api_url = self.env['connect.settings'].get_param('api_url')
        fallback_url = self.env['connect.settings'].get_param('api_fallback_url')
        for rec in self:
            rec.voice_status_url = urljoin(api_url, 'telnyx/webhook/callstatus')
            rec.voice_url = urljoin(api_url, 'telnyx/webhook/texml/{}'.format(rec.id))
            if fallback_url:
                rec.voice_fallback_url = urljoin(fallback_url, 'telnyx/webhook/texml/{}'.format(rec.id))
            else:
                rec.voice_fallback_url = ''

    @api.constrains('texpy')
    def _check_syntax(self):
        if self.code_type == 'texpy' and self.texpy:
            self.render()

    def render(self, request=None, params=None):
        # Copy into fresh dicts so shared defaults are never mutated
        # across requests.
        request = dict(request or {})
        params = dict(params or {})
        self = self.sudo()
        api_url_check = self.env['connect.settings'].check_api_url()
        if api_url_check:
            return self.env[
                'connect.settings'].telnyx_apply_system_voice(
                    '<Response><Say>{}</Say></Response>'.format(api_url_check))
        self.ensure_one()
        api_url = self.env['connect.settings'].sudo().get_param('api_url')
        recording_voice_status_url = urljoin(api_url, 'telnyx/webhook/recordingstatus')
        call_voice_status_url = urljoin(api_url, 'telnyx/webhook/callstatus')
        params.update({
            'recording_voice_status_url': recording_voice_status_url,
            'call_voice_status_url': call_voice_status_url,
        })
        if self.code_type == 'texml':
            res = self.render_texml(request=request, params=params)
        elif self.code_type == 'texpy':
            res = self.render_python(request=request, params=params)
        elif self.code_type == 'model_method':
            res = str(getattr(self.env[self.model], self.method)(request=request, params=params))
        res = self.env[
            'connect.settings'].sudo().telnyx_apply_system_voice(res)
        debug(self, 'TeXML render result: %s' % pretty_xml(res))
        return res

    def render_texml(self, request=None, params=None):
        environment = jinja2.Environment()
        template = environment.from_string(self.texml)
        # Merge into a local dict instead of mutating the caller's request.
        ctx = dict(request or {})
        ctx.update(params or {})
        res = template.render(**ctx)
        return res

    def render_python(self, request=None, params=None):
        from . import texml_response
        request = dict(request or {})
        params = dict(params or {})
        try:
            exec(self.texpy, {}, {
                'logger': logger,
                'request': request,
                'params': params,
                'texml': texml_response,
                'user': self.env.user,
                'context': self.env.context,
                'env': self.env,
                'rec': self,
                'self': self,
                'pretty_xml': pretty_xml,
                'random': random,
                'datetime': datetime,
                'time': time,
            })
            return self.texml
        except Exception as e:
            logger.exception('TeXML render error:')
            raise ValidationError(str(e))

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.telnyx.exten'].create_extension(self, self._name)

    @api.onchange('code_type')
    def _set_default_texpy_code(self):
        if self.code_type == 'texpy' and not self.texpy:
            self.texpy = """from odoo.addons.connect_telnyx.models.texml_response import VoiceResponse, Dial, Gather

# datetime: Python datetime library.
# logger: logger - logger.info('test')
# random: Python random library.
# request: request - dict, call data from the Telnyx request.
# params: params - dict, additional params set by the request handler.
# time: Python time library.
# texml: texml - the connect_telnyx TeXML builder module.
# self: current TeXPy recordset.

response = VoiceResponse()
user_name = self.env.user.name
response.say('Welcome {} to the world of Connect!'.format(user_name))
self.texml = response
"""
