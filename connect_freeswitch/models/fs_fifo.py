import logging
import re
from odoo import api, fields, models

logger = logging.getLogger(__name__)


class FsFifo(models.Model):
    _name = 'connect.fs_fifo'
    _description = 'FS Queue'
    _order = 'name'

    name = fields.Char(required=True)
    exten = fields.Many2one('connect.exten', ondelete='set null', readonly=True)
    exten_number = fields.Char(related='exten.number', store=True)
    max_wait_time = fields.Integer(
        default=60,
        help='Maximum time (in seconds) a caller waits in the queue before fallback.',
    )
    moh_sound = fields.Char(
        string='Music on Hold',
        default='$${hold_music}',
        help='FreeSWITCH sound source played while the caller is waiting. '
             'Defaults to the global `hold_music` variable defined in vars.xml '
             '(silence_stream://0 out of the box).',
    )
    member_user_ids = fields.Many2many(
        'connect.user', 'fs_fifo_user_rel', 'fifo_id', 'user_id',
        string='User Agents',
    )
    member_endpoint_ids = fields.Many2many(
        'connect.endpoint', 'fs_fifo_endpoint_rel', 'fifo_id', 'endpoint_id',
        string='Endpoint Agents',
    )
    timeout_action = fields.Selection(
        [('hangup', 'Hangup'),
         ('voicemail', 'Voicemail'),
         ('transfer', 'Transfer to Extension')],
        default='hangup', required=True,
    )
    voicemail_user_id = fields.Many2one(
        'connect.user', ondelete='set null',
        help='User whose voicemail box is used after queue timeout '
             '(required when timeout_action = voicemail).',
    )
    fallback_exten_id = fields.Many2one(
        'connect.exten', ondelete='set null',
        help='Extension to transfer the caller after queue timeout '
             '(required when timeout_action = transfer).',
    )
    record_calls = fields.Boolean(default=False)

    # Fields whose change alters the generated fifo.conf (mod_fifo consumers),
    # so FreeSWITCH must re-read it for the change to take effect (ADR-027).
    _FIFO_RELOAD_FIELDS = ('member_user_ids', 'member_endpoint_ids', 'max_wait_time')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._trigger_fifo_reload()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in self._FIFO_RELOAD_FIELDS):
            self._trigger_fifo_reload()
        return res

    def unlink(self):
        self._trigger_fifo_reload()
        return super().unlink()

    def _trigger_fifo_reload(self):
        """Schedule one post-commit ``reload mod_fifo`` so FreeSWITCH re-reads
        fifo.conf after this queue's members/config change.

        Deferred to after commit because FreeSWITCH re-fetches fifo.conf over
        xml_curl on a separate connection — it must see committed data. Deduped
        per transaction via the postcommit callback registry.
        """
        callbacks = self.env.cr.postcommit
        if not callbacks.data.get('connect_fs_fifo_reload'):
            callbacks.data['connect_fs_fifo_reload'] = True
            callbacks.add(self._do_fifo_reload)

    def _do_fifo_reload(self):
        """Best-effort ``reload mod_fifo`` — never break the save if FS is down."""
        try:
            self.env['connect.settings'].sudo().freeswitch_api('reload', 'mod_fifo')
        except Exception:
            logger.exception('FS Queue: reload mod_fifo failed')

    def create_extension(self):
        self.ensure_one()
        return self.env['connect.exten'].create_extension(self, 'fs_fifo')

    def _member_dial_string(self, fs_domain, user=None, endpoint=None):
        """Build FreeSWITCH dial-string for a queue member."""
        if user is not None:
            if not user.exten_number:
                return ''
            return 'user/{}@{}'.format(user.exten_number, fs_domain)
        if endpoint is not None:
            target = endpoint.auth_user or endpoint.exten_number
            if not target:
                return ''
            return 'user/{}@{}'.format(target, fs_domain)
        return ''

    def _dialplan_target(self):
        """Destination FreeSWITCH dials to reach this queue.

        The user-facing extension if one is assigned, else the internal
        ``fs_fifo_<id>`` handle — so the queue is always routable as a
        callflow/IVR fallback without requiring a numbered extension
        (the controller resolves ``fs_fifo_<id>`` back to this record).
        """
        self.ensure_one()
        return self.exten_number or 'fs_fifo_%d' % self.id

    def generate_dialplan(self, params, exten=None):
        """Generate FreeSWITCH dialplan XML for this FIFO queue."""
        self.ensure_one()
        number = exten.number if exten else self._dialplan_target()

        fs_domain = self.env['connect.settings'].sudo().get_param(
            'freeswitch_domain') or '${domain}'

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        recording_url = ''
        if self.record_calls and base_url:
            recording_url = '{}freeswitch/webhook/recording'.format(
                base_url if base_url.endswith('/') else base_url + '/')

        members = []
        for user in self.member_user_ids:
            dial_string = self._member_dial_string(fs_domain, user=user)
            if dial_string:
                members.append({'dial_string': dial_string})
        for endpoint in self.member_endpoint_ids:
            dial_string = self._member_dial_string(fs_domain, endpoint=endpoint)
            if dial_string:
                members.append({'dial_string': dial_string})

        timeout_action = self.timeout_action or 'hangup'
        voicemail_user_number = ''
        fallback_number = ''
        if timeout_action == 'voicemail':
            vm_user = self.voicemail_user_id or (
                self.member_user_ids[:1] if self.member_user_ids else False)
            if vm_user:
                voicemail_user_number = vm_user.exten_number or ''
            if not voicemail_user_number:
                timeout_action = 'hangup'
        elif timeout_action == 'transfer':
            if self.fallback_exten_id and self.fallback_exten_id.number:
                fallback_number = self.fallback_exten_id.number
            else:
                timeout_action = 'hangup'

        return self.env['connect.freeswitch.template'].render('dialplan_fs_fifo', {
            'fifo_id': self.id,
            'fifo_name': 'fs_fifo_{}'.format(self.id),
            'number': re.escape(number),
            'exten_id': exten.id if exten else None,
            'max_wait': self.max_wait_time or 60,
            'moh': self.moh_sound or '$${hold_music}',
            'record_calls': bool(self.record_calls),
            'recording_url': recording_url,
            'members': members,
            'timeout_action': timeout_action,
            'voicemail_user': voicemail_user_number,
            'fallback_number': fallback_number,
        })
