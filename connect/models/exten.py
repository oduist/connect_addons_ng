import logging
from odoo import fields, models, api
from odoo.models import Constraint

logger = logging.getLogger(__name__)


class Exten(models.Model):
    _name = 'connect.exten'
    _description = 'Exten'
    _order = 'number'

    name = fields.Char(compute='_get_name', copy=False)
    number = fields.Char('Extension Number', required=True, copy=False)
    provider_id = fields.Many2one(
        'connect.provider', ondelete='set null', index=True, copy=False,
        help='Telephony provider that renders this extension.',
    )
    model = fields.Char('AppModel')
    model_friendly = fields.Char('Model', compute='_get_model_friendly', store=True, copy=False)
    res_id = fields.Integer()
    dst = fields.Reference(
        string='Destination',
        ondelete='cascade',
        required=False,
        selection=[
            ('connect.user', 'User'),
            ('connect.callflow', 'Call Flow'),
        ],
        compute='_get_dst', inverse='_set_dst')
    dst_name = fields.Char(compute='_get_dst')

    _number_uniq = Constraint('UNIQUE(number)', 'This extension number is already defined in the domain!')

    def _get_name(self):
        for rec in self:
            try:
                rec.name = "{} <{}>".format(rec.number, rec.dst.name if rec.dst else '')
            except Exception as e:
                logger.exception('Exten name error:')
                rec.name = 'See Odoo Error Log'

    @api.depends('model')
    def _get_model_friendly(self):
        for rec in self:
            try:
                rec.model_friendly = dict(
                    self.env['connect.exten']._fields['dst'].selection).get(rec.model)
            except Exception as e:
                logger.exception('Exten Model friendly error:')
                rec.model_friendly = ''

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            exten = self.search([('number', '=', vals['number'])])
            if exten and not exten.dst:
                exten.write(vals)
                return exten
        res = super().create(vals_list)
        for record in res:
            if hasattr(record.dst, 'exten'):
                record.dst.exten = record
        return res

    def write(self, vals):
        if (self.model is not False) and ('model' in vals) and ('res_id' in vals):
            self.env[self.model].search([('exten', '=', self.id)]).update({'exten': False})
            self.env['connect.exten'].search([
                ('res_id', '=', vals['res_id']), ('model', '=', vals['model'])]).update({'res_id': False})
        res = super().write(vals)
        if hasattr(self.dst, 'exten'):
            self.dst.exten = self
        return res

    def unlink(self):
        for rec in self:
            if hasattr(rec.dst, 'exten'):
                rec.dst.exten = False
        return super().unlink()

    def copy_data(self, default=None):
        default = dict(default or {})
        data_list = super().copy_data(default)
        extensions = self.search([('model', '=', data_list[0]['model'])])
        last_number = extensions[-1].number
        new_number = int(last_number) + 1
        data_list[0]['number'] = str(new_number)
        return data_list

    def _get_dst(self):
        for rec in self:
            if rec.model and rec.model in self.env:
                try:
                    rec.dst = '%s,%s' % (rec.model, rec.res_id or 0)
                    rec.dst_name = self.env[rec.model]._description
                except ValueError as e:
                    logger.error('Exten dst error: %s', e)
                    rec.dst = None
                    rec.dst_name = None
            else:
                rec.dst = None
                rec.dst_name = None

    def _set_dst(self):
        for rec in self:
            if rec.dst:
                rec.write({'model': rec.dst._name, 'res_id': rec.dst.id})
                if hasattr(rec.dst, 'exten'):
                    rec.dst.exten = rec
            else:
                rec.write({'model': False, 'res_id': False})

    @api.model
    def create_extension(self, rec, ext_type):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'connect.exten',
            'view_mode': 'form',
            'res_id': rec.exten.id if rec.exten else False,
            'target': 'new' if not rec.exten else 'current',
            'context': {
                'default_dst': 'connect.{},{}'.format(ext_type, rec.id)
            }
        }
