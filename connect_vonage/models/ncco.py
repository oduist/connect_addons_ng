# -*- coding: utf-8 -*-
import datetime
import json
import logging
import random
import time

import jinja2

from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

DEFAULT_NCCO = json.dumps(
    [{'action': 'talk', 'text': 'Hello from Odoo Connect!'}], indent=2)


class Ncco(models.Model):
    """NCCO application — the Vonage counterpart of a TwiML app.

    Unlike Twilio applications, NCCO apps are pure server-side content:
    there is no Vonage-side resource to create or sync. render() returns a
    Python list; webhook controllers serialize it as application/json.
    """
    _name = 'connect.ncco'
    _description = 'NCCO app'
    _order = 'name'

    name = fields.Char(required=True)
    description = fields.Text()
    code_type = fields.Selection([
        ('ncco', 'NCCO'),
        ('nccopy', 'NccoPy'),
        ('model_method', 'model.method')
    ], help='NCCO is a JSON document (jinja2-templated). NccoPy is Python '
            'code that must assign a list to the "ncco" variable. To call '
            'mymodel.render() set mymodel.render as model.method.',
        required=True, default='ncco')
    ncco = fields.Text(required=True, string='NCCO', default=DEFAULT_NCCO)
    nccopy = fields.Text('NccoPy')
    model = fields.Char()
    method = fields.Char()
    answer_url = fields.Char(compute='_get_vonage_urls', compute_sudo=True)
    exten = fields.Many2one('connect.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number')

    def _get_vonage_urls(self):
        for rec in self:
            rec.answer_url = self.env['connect.settings'].get_vonage_webhook_url(
                'ncco/{}'.format(rec.id))

    @api.constrains('ncco')
    def _check_ncco_syntax(self):
        for rec in self:
            if rec.code_type == 'ncco' and rec.ncco and '{{' not in rec.ncco:
                # Static documents must at least be valid JSON. Templated
                # ones can only be validated at render time.
                try:
                    json.loads(rec.ncco)
                except ValueError as e:
                    raise ValidationError(
                        'Invalid NCCO JSON: {}'.format(e))

    def render(self, request=None, params=None):
        """Render the NCCO app. Returns a list of NCCO actions."""
        request = dict(request or {})
        params = dict(params or {})
        self = self.sudo()
        api_url_check = self.env['connect.settings'].check_api_url()
        if api_url_check:
            return [{'action': 'talk', 'text': api_url_check}]
        self.ensure_one()
        params.update({
            'event_url': self.env['connect.settings'].get_vonage_webhook_url(
                'event'),
            'recording_url': self.env[
                'connect.settings'].get_vonage_webhook_url('recording'),
        })
        if self.code_type == 'ncco':
            res = self.render_ncco(request=request, params=params)
        elif self.code_type == 'nccopy':
            res = self.render_python(request=request, params=params)
        elif self.code_type == 'model_method':
            res = getattr(self.env[self.model], self.method)(
                request=request, params=params)
        debug(self, 'NCCO render result: %s' % json.dumps(res, indent=2))
        return res

    def render_ncco(self, request=None, params=None):
        environment = jinja2.Environment()
        template = environment.from_string(self.ncco)
        ctx = dict(request or {})
        ctx.update(params or {})
        res = template.render(**ctx)
        try:
            return json.loads(res)
        except ValueError as e:
            logger.error('NCCO render error: %s', e)
            raise ValidationError('Rendered NCCO is not valid JSON: {}'.format(e))

    def render_python(self, request=None, params=None):
        request = dict(request or {})
        params = dict(params or {})
        local_vars = {
            'logger': logger,
            'request': request,
            'params': params,
            'user': self.env.user,
            'context': self.env.context,
            'env': self.env,
            'rec': self,
            'self': self,
            'random': random,
            'datetime': datetime,
            'time': time,
            'json': json,
            'ncco': [],
        }
        try:
            exec(self.nccopy, {}, local_vars)
            result = local_vars.get('ncco') or []
            if not isinstance(result, list):
                raise ValidationError('NccoPy must assign a list to "ncco"!')
            return result
        except ValidationError:
            raise
        except Exception as e:
            logger.exception('NCCO render error:')
            raise ValidationError(str(e))

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.exten'].create_extension(self, 'ncco')

    @api.onchange('code_type')
    def _set_default_nccopy_code(self):
        if self.code_type == 'nccopy' and not self.nccopy:
            self.nccopy = """# Build the NCCO action list and assign it to the ncco variable.
# datetime: Python datetime library.
# logger: logger - logger.info('test')
# random: Python random library.
# request: dict, call data from the Vonage answer request.
# params: dict, additional params set by the request handler.
# time: Python time library.
# json: Python json library.
# self: current NCCO recordset.

ncco = [
    {'action': 'talk',
     'text': 'Welcome {} to the world of Connect!'.format(self.env.user.name)},
]
"""
