import logging

from odoo import api, fields, models
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
             'connect.provider.elevenlabs.config. Twilio and FreeSWITCH '
             'keep their settings on connect.settings (ADR-031).',
    )
    webhook_user_id = fields.Many2one(
        'res.users', string='Webhook User', ondelete='restrict',
        help='Technical user that executes incoming webhook requests for '
             'this provider. Falls back to connect.user_connect_webhook '
             'when empty (the historical shared webhook user). Set a '
             'per-provider user when fine-grained access control or '
             'audit separation is required (ODU-16 / ADR-023 Phase 7).',
    )

    _code_uniq = Constraint('UNIQUE(code)', 'Provider code must be unique.')

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

    def _webhook_user(self):
        """Resolve the technical user that should execute webhook
        requests for this provider. Falls back to the shared
        connect.user_connect_webhook record when no per-provider user
        is set."""
        self.ensure_one()
        if self.webhook_user_id:
            return self.webhook_user_id
        try:
            return self.env.ref('connect.user_connect_webhook')
        except ValueError:
            return self.env['res.users']

    def _phone_adapter_module(self):
        """Return the asset path of the JS module that registers this
        provider's PhoneAdapter into the `connect.phone_adapters`
        client-side registry (ODU-8 / ADR-023 Pillar 5).

        Returns False when the provider has no UI phone widget.
        Today's two-systray world is the legacy; the eventual single
        core PhoneSystray will load adapters via this resolution path.
        """
        return False

    def _active_calls_tray_module(self):
        """Asset path of the JS module that contributes this provider's
        rows to the unified active-calls tray (ODU-9). Returns False
        when there is no contribution."""
        return False

    def _message_action_modules(self):
        """Return a list of asset paths for the JS modules that
        register this provider's mail-message actions
        (SMS/WhatsApp/etc. reply buttons) into the unified
        `connect.message_actions` registry (ODU-9)."""
        return []

    def _get_webrtc_config(self, user=None):
        """Return WebRTC bootstrap config for the given (or current)
        user. Each provider implements its own native shape (FS Verto,
        Twilio Voice JS, …). The `/connect/webrtc/config` controller
        resolves the user's active provider and dispatches via this
        method (ODU-10 / ADR-023 Pillar 5).

        Returns a JSON-serialisable dict. When no provider is willing
        to provide WebRTC for this user (no enabled binding, missing
        config, …), returns `{'enabled': False, 'reason': '...'}`.
        """
        return {'enabled': False, 'reason': 'no_provider_impl'}

    def _verify_webhook(self, request, data=None):
        """Unified webhook authentication (ADR-023 Phase 7 / ODU-15).

        Each provider implements this with its native mechanism:
          - Twilio: HMAC signature (`X-Twilio-Signature`)
          - FreeSWITCH: bearer token in Authorization header
          - ElevenLabs: token in `x-elevenlabs-agent-token`

        Returns True if the request is authentic. Reaching this base
        means no installed provider override matched the dispatch code
        — return False (deny) and log.
        """
        _logger = logging.getLogger('connect.webhook')
        _logger.warning(
            'webhook verify denied: provider %r has no _verify_webhook impl',
            self.code,
        )
        return False
