import jinja2
import logging
from odoo import api, fields, models, release, tools
if release.version_info[0] >= 19:
    from odoo.models import Constraint

logger = logging.getLogger(__name__)


class FreeSwitchTemplate(models.Model):
    _name = 'connect.freeswitch.template'
    _description = 'FreeSWITCH XML Template'
    _order = 'key'

    key = fields.Char(required=True, readonly=True, copy=False)
    name = fields.Char(required=True)
    description = fields.Text(readonly=True,
        help='Documents the available Jinja2 context variables for this template')
    section = fields.Selection([
        ('directory', 'Directory'),
        ('dialplan', 'Dialplan'),
        ('configuration', 'Configuration'),
    ], required=True, readonly=True)
    content = fields.Text(required=True)
    default_content = fields.Text(readonly=True)
    is_customized = fields.Boolean(compute='_compute_is_customized', store=True)

    if release.version_info[0] >= 19:
        _key_uniq = Constraint('UNIQUE(key)', 'Template key must be unique!')
    else:
        _sql_constraints = [
            ('key_uniq', 'UNIQUE(key)', 'Template key must be unique!'),
        ]

    @api.depends('content', 'default_content')
    def _compute_is_customized(self):
        for rec in self:
            rec.is_customized = (rec.content or '') != (rec.default_content or '')

    def write(self, vals):
        result = super().write(vals)
        if 'content' in vals:
            self._get_template_content.clear_cache(self)
        return result

    def unlink(self):
        self._get_template_content.clear_cache(self)
        return super().unlink()

    def reset_to_default(self):
        for rec in self:
            rec.content = rec.default_content

    @tools.ormcache('key')
    def _get_template_content(self, key):
        rec = self.sudo().search([('key', '=', key)], limit=1)
        if not rec:
            return None
        return rec.content

    @api.model
    def render(self, key, context):
        """Look up template by key and render with the given context dict."""
        content = self._get_template_content(key)
        if content is None:
            raise ValueError("FreeSWITCH template '{}' not found".format(key))
        env = jinja2.Environment(
            autoescape=False,
            undefined=jinja2.StrictUndefined,
        )
        tmpl = env.from_string(content)
        return tmpl.render(**context)
