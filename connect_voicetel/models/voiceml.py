# -*- coding: utf-8 -*-
import datetime
import jinja2
import logging
import random
import time
from xml.dom.minidom import parseString
from voiceml.exceptions import NotFoundError
from voiceml.models import CreateApplicationRequest, UpdateApplicationRequest

from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


def pretty_xml(content):
    try:
        dom = parseString(str(content))
        pretty_content = dom.toprettyxml()
        return "\n".join([line for line in pretty_content.splitlines() if line.strip()])
    except Exception as e:
        logger.error('Pretty XML parse error: %s', e)
        return 'Pretty XML parse error: {}\n{}'.format(e, str(content))


class VoiceML(models.Model):
    """A VoiceML application: the VoiceTel counterpart of a TwiML app.

    Each record is mirrored as an Application resource on the VoiceML
    account; its voice URL points back at /voicetel/webhook/voiceml/<id>.
    """
    _name = 'connect.voicetel.voiceml'
    _description = 'VoiceML app'
    _order = 'name'

    sid = fields.Char('SID', readonly=True)
    name = fields.Char(required=True)
    description = fields.Text()
    code_type = fields.Selection([
        ('voiceml', 'VoiceML'),
        ('python', 'Python'),
        ('model_method', 'model.method')
    ], help='Type of the application. To call mymodel.render() set mymodel.render as model.method',
        required=True, default='voiceml')
    voiceml = fields.Text(required=True, string='VoiceML',
        default=pretty_xml('<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello</Say></Response>'))
    python_code = fields.Text('Python')
    model = fields.Char()
    method = fields.Char()
    voice_url = fields.Char(compute='_get_voicetel_urls', compute_sudo=True)
    voice_fallback_url = fields.Char(compute='_get_voicetel_urls', compute_sudo=True)
    voice_status_url = fields.Char(compute='_get_voicetel_urls', compute_sudo=True)
    exten = fields.Many2one('connect.voicetel.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number')

    def create_voicetel_app(self, client):
        self.ensure_one()
        application = client.applications.create(CreateApplicationRequest(
            VoiceUrl=self.voice_url,
            VoiceFallbackUrl=self.voice_fallback_url,
            FriendlyName=self.name,
            StatusCallback=self.voice_status_url,
        ))
        self.write({'sid': application.sid})
        debug(self, 'Created VoiceML app {}.'.format(self.name))
        return application

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get('install_mode') or self.env.context.get(
                'no_voicetel_create'):
            return records
        if not self.env["connect.settings"].get_param("voicetel_auto_sync"):
            return records
        client = self.env['connect.settings'].get_voicetel_client()
        for rec in records:
            rec.create_voicetel_app(client)
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env["connect.settings"].get_param("voicetel_auto_sync"):
            return res
        if self.env.context.get('skip_voicetel_sync'):
            return res
        if not (set(['name', 'code_type', 'model', 'method']) & set(vals.keys())):
            return res
        client = self.env['connect.settings'].get_voicetel_client()
        for rec in self:
            rec.update_voicetel_app(client)
        return res

    def update_voicetel_app(self, client):
        """Push this record to its Application; create it when it is gone.

        The application is looked up by SID only -- never re-created on an
        unrelated failure -- so a sync cannot leave orphan Applications
        behind.
        """
        self.ensure_one()
        if not self.sid:
            return self.create_voicetel_app(client)
        try:
            application = client.applications.update(
                self.sid, UpdateApplicationRequest(
                    VoiceUrl=self.voice_url,
                    VoiceFallbackUrl=self.voice_fallback_url,
                    FriendlyName=self.name,
                    StatusCallback=self.voice_status_url,
                ))
            debug(self, 'VoiceML app {} updated.'.format(self.name))
            return application
        except NotFoundError:
            debug(self, 'VoiceML app {} (SID {}) not found, creating.'.format(
                self.name, self.sid))
            return self.create_voicetel_app(client)

    def unlink(self):
        if not self.env["connect.settings"].get_param("voicetel_auto_sync"):
            return super().unlink()
        client = self.env['connect.settings'].get_voicetel_client()
        for rec in self:
            if rec.sid:
                try:
                    client.applications.delete(rec.sid)
                except NotFoundError:
                    logger.warning('Cannot delete app %s in VoiceML, not found', rec.name)
        return super().unlink()

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_voicetel_client()
        for rec in self.search([]):
            rec.update_voicetel_app(client)

    def _get_voicetel_urls(self):
        settings = self.env['connect.settings'].sudo()
        fallback_url = settings.get_param('api_fallback_url')
        for rec in self:
            rec.voice_status_url = settings.voicetel_webhook_url('voicetel/webhook/callstatus')
            rec.voice_url = settings.voicetel_webhook_url(
                'voicetel/webhook/voiceml/{}'.format(rec.id))
            if fallback_url:
                rec.voice_fallback_url = '{}/voicetel/webhook/voiceml/{}'.format(
                    fallback_url.rstrip('/'), rec.id)
            else:
                rec.voice_fallback_url = ''

    @api.constrains('python_code')
    def _check_syntax(self):
        for rec in self:
            if rec.code_type == 'python' and rec.python_code:
                rec.render()

    def render(self, request=None, params=None):
        # Copy into fresh dicts so that nothing mutates the caller's state.
        request = dict(request or {})
        params = dict(params or {})
        self = self.sudo()
        api_url_check = self.env['connect.settings'].check_api_url()
        if api_url_check:
            return '<Response><Say>{}</Say></Response>'.format(api_url_check)
        self.ensure_one()
        settings = self.env['connect.settings'].sudo()
        params.update({
            'recording_voice_status_url': settings.voicetel_webhook_url(
                'voicetel/webhook/recordingstatus'),
            'call_voice_status_url': settings.voicetel_webhook_url(
                'voicetel/webhook/callstatus'),
        })
        if self.code_type == 'voiceml':
            res = self.render_voiceml(request=request, params=params)
        elif self.code_type == 'python':
            res = self.render_python(request=request, params=params)
        elif self.code_type == 'model_method':
            res = str(getattr(self.env[self.model], self.method)(request=request, params=params))
        debug(self, 'VoiceML render result: %s' % pretty_xml(res))
        return res

    def render_voiceml(self, request=None, params=None):
        environment = jinja2.Environment()
        template = environment.from_string(self.voiceml)
        ctx = dict(request or {})
        ctx.update(params or {})
        return template.render(**ctx)

    def render_python(self, request=None, params=None):
        from . import voiceml_response
        request = dict(request or {})
        params = dict(params or {})
        try:
            exec(self.python_code, {}, {
                'logger': logger,
                'request': request,
                'params': params,
                'voiceml': voiceml_response,
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
            return self.voiceml
        except Exception as e:
            logger.exception('VoiceML render error:')
            raise ValidationError(str(e))

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.voicetel.exten'].create_extension(self, self._name)

    @api.onchange('code_type')
    def _set_default_python_code(self):
        if self.code_type == 'python' and not self.python_code:
            self.python_code = """from odoo.addons.connect_voicetel.models.voiceml_response import VoiceResponse, Dial, Gather

# datetime: Python datetime library.
# logger: logger - logger.info('test')
# random: Python random library.
# request: request - dict, call data from the VoiceML request.
# params: params - dict, additional params set by the request handler.
# time: Python time library.
# voiceml: the module's VoiceML builder (VoiceResponse, Dial, Gather, ...).
# self: current VoiceML app recordset.

response = VoiceResponse()
user_name = self.env.user.name
response.say('Welcome {} to the world of Connect!'.format(user_name))
self.voiceml = response
"""
