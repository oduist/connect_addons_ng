"""ElevenLabs per-provider configuration singleton (ADR-023 Phase 6).

Moves Twilio-style settings off the flat `connect.settings` notebook into
a dedicated model owned by `connect_elevenlabs`. The display-mask pattern
(`display_X` field stores the public-facing `****`, real `X` holds the
secret in a privileged group) is reproduced locally — it's a generic
pattern from `connect.settings.write` but the new model needs its own
implementation.

The singleton record is created on first access via `_get()` and is the
target of:
- `_compute_post_call_webhook_url` (URL the EL post-call webhook should POST to)
- `_compute_conversation_initiation_webhook_url` (ADR-021 init webhook)
- All EL-specific actions previously on `connect.settings`
  (`reset_token`, `unbind_account`, `sync`, `sync_tools`,
  `regenerate_prompts`, `get_voices`).
"""
import logging
import uuid
from urllib.parse import urljoin

from elevenlabs import ElevenLabs

from odoo import api, fields, models
from odoo.exceptions import ValidationError

logger = logging.getLogger(__name__)

PROTECTED_FIELDS = {
    'display_api_key',
    'display_post_call_webhook_secret',
}


class ConnectProviderElevenLabsConfig(models.Model):
    _name = 'connect.provider.elevenlabs.config'
    _description = 'ElevenLabs Provider Configuration'

    enabled = fields.Boolean()
    api_key = fields.Char(groups="base.group_erp_manager")
    display_api_key = fields.Char()
    agent_token = fields.Char(
        required=True, groups="base.group_erp_manager",
        default=lambda x: str(uuid.uuid4()),
    )
    voice = fields.Many2one(
        'connect.elevenlabs_voice', ondelete='set null',
        string='Selected Voice',
    )

    post_call_webhook_url = fields.Char(compute='_compute_post_call_webhook_url')
    post_call_webhook_secret = fields.Char(groups="base.group_erp_manager")
    display_post_call_webhook_secret = fields.Char()
    conversation_initiation_webhook_url = fields.Char(
        compute='_compute_conversation_initiation_webhook_url',
    )

    @api.model
    def _get(self):
        """Singleton accessor. Creates the record on first use."""
        rec = self.sudo().search([], limit=1)
        if not rec:
            rec = self.sudo().with_context(skip_protected_fields=True).create({})
        return rec

    def _compute_post_call_webhook_url(self):
        api_url = (self.env['connect.settings'].sudo().get_param('api_url') or '').strip()
        for rec in self:
            rec.post_call_webhook_url = urljoin(api_url, 'connect_elevenlabs/post_call')

    def _compute_conversation_initiation_webhook_url(self):
        api_url = (self.env['connect.settings'].sudo().get_param('api_url') or '').strip()
        for rec in self:
            rec.conversation_initiation_webhook_url = urljoin(
                api_url, 'connect_elevenlabs/conversation_init')

    def write(self, vals):
        if self.env.context.get('skip_protected_fields'):
            return super().write(vals)
        res = super().write(vals)
        changed = {}
        for fname in PROTECTED_FIELDS:
            if vals.get(fname):
                value = vals[fname]
                changed[fname.replace('display_', '')] = value
                changed[fname] = '*' * len(value)
        if changed:
            self.with_context(skip_protected_fields=True).sudo().write(changed)
        return res

    def get_client(self):
        """Return an authenticated ElevenLabs SDK client."""
        key = self.sudo().api_key
        if not key:
            raise ValidationError('ElevenLabs API key not set!')
        return ElevenLabs(api_key=key)

    def get_voices(self):
        self.env['connect.elevenlabs_voice'].get_voices()

    def regenerate_prompts(self):
        self.env['connect.callflow'].elevenlabs_regenerate_prompts()

    def sync_agents(self):
        self.env['connect.elevenlabs_agent'].sync()

    def reset_token(self):
        """Rotate the agent token and re-push the init webhook config."""
        self.sudo().agent_token = str(uuid.uuid4())
        self._push_initiation_webhook()

    def sync_tools(self):
        """Sync all tools to ElevenLabs (create or update). System tools
        are excluded — they are managed via agent config (PATCH agent)."""
        tools = self.env['connect.elevenlabs_agent_tool'].search([('tool_type', '!=', 'system')])
        for tool in tools:
            if tool.tool_id:
                tool.update_elevenlabs_tool()
            else:
                tool._sync_to_elevenlabs()
        self.env['connect.settings'].connect_notify(
            'Tools sync done!', title='Elevenlabs Agent',
            notify_uid=self.env.user.id,
        )

    def sync(self):
        if not self.env['oduist.license'].check_license('connect_elevenlabs', silent=True):
            return False
        self.get_voices()
        Settings = self.env['connect.settings']
        Settings.connect_notify('Voices sync done!', title='Elevenlabs Agent',
                                notify_uid=self.env.user.id)
        self.reset_token()
        self.sync_tools()
        for agent in self.env['connect.elevenlabs_agent'].search([]):
            agent.update_elevenlabs_agent()
        Settings.connect_notify('Sync done', title='Elevenlabs Agent',
                                notify_uid=self.env.user.id)

    def unbind_account(self):
        """Sync with new ElevenLabs account: clear agent and tool IDs."""
        self.env['connect.elevenlabs_agent'].with_context(skip_elevenlabs=True).search([]).write({
            'agent_uid': None,
            'el_virtual_number_uid': False,
        })
        self.env['connect.elevenlabs_agent_tool'].with_context(skip_elevenlabs=True).search([]).write(
            {'tool_id': None, 'synced': False})
        self.env['connect.settings'].connect_notify(
            'Unbind done!', title='Elevenlabs Agent', notify_uid=self.env.user.id,
        )

    def _push_initiation_webhook(self):
        """Push the Conversation Initiation Client Data Webhook to EL workspace settings.

        Workspace-level webhook (PATCH /v1/convai/settings) — one config
        for all agents in the account. URL and token come from this
        record; agent-level overrides are intentionally not used
        (ADR-021)."""
        rec = self.sudo()
        if not rec.enabled:
            return
        url = rec.conversation_initiation_webhook_url
        token = rec.agent_token
        if not url or not token:
            return
        try:
            client = rec.get_client()
        except ValidationError:
            return
        try:
            client.conversational_ai.settings.update(
                conversation_initiation_client_data_webhook={
                    'url': url,
                    'request_headers': {
                        'x-elevenlabs-agent-token': token,
                    },
                },
            )
            logger.info("EL initiation webhook pushed: %s", url)
        except Exception as e:
            logger.exception("EL initiation webhook push failed: %s", e)

    def action_open_form(self):
        rec = self._get()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': rec.id,
            'name': 'ElevenLabs',
            'view_mode': 'form',
            'view_id': self.env.ref('connect_elevenlabs.connect_elevenlabs_settings_form').id,
            'target': 'current',
        }
