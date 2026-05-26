from odoo import api, fields, models, release

if release.version_info[0] >= 19:
    from odoo.models import Constraint


class ConnectProvider(models.Model):
    _name = 'connect.provider'
    _description = 'Telephony provider'
    _order = 'sequence, code'

    code = fields.Char(required=True, copy=False, index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    config_model = fields.Char(
        help='Technical name of the per-provider config model, e.g. '
             'connect.provider.twilio.config.',
    )

    if release.version_info[0] >= 19:
        _code_uniq = Constraint('UNIQUE(code)', 'Provider code must be unique.')
    else:
        _sql_constraints = [
            ('code_uniq', 'UNIQUE(code)', 'Provider code must be unique.'),
        ]

    @api.model
    def _register_code(self, code, name, sequence=10, config_model=None):
        """Idempotent upsert of a provider entry, keyed by `code`.

        Named `_register_code` (not `_register`) because `BaseModel._register`
        is a framework-level boolean attribute used by Odoo's class-resolution
        machinery — shadowing it breaks model instantiation.
        """
        rec = self.with_context(active_test=False).search([('code', '=', code)], limit=1)
        vals = {'name': name, 'active': True}
        if config_model is not None:
            vals['config_model'] = config_model
        if rec:
            rec.write(vals)
            return rec
        return self.create({'code': code, 'sequence': sequence, **vals})

    @api.model
    def _deactivate(self, code):
        rec = self.with_context(active_test=False).search([('code', '=', code)], limit=1)
        if rec:
            rec.active = False

    @api.model
    def _default(self):
        return self.search([], limit=1)

    @api.model
    def _for_user(self, user):
        return self.search([])

    def _for_record(self, record):
        if 'provider_id' in record._fields and record.provider_id:
            return record.provider_id
        return self.browse()

    # ---------------------------------------------------------------
    # Provider-method abstracts. Each provider module inherits this
    # class and overrides the methods it supports, guarding the body
    # with `if self.code != 'xxx': return super()._method(...)` so the
    # dispatch chain walks through every installed provider until the
    # one matching the recordset's code handles the call.
    # ---------------------------------------------------------------

    def _originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        """Outbound call origination. Concrete implementation lives on
        each provider module (TwilioProvider, FreeSwitchProvider, …).
        Reaching this base means no installed provider claimed the
        dispatch — likely a misconfigured `connect.provider` record."""
        raise NotImplementedError(
            f'Provider {self.code!r} does not implement _originate_call'
        )
