# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import models, fields, api, release
from odoo.exceptions import ValidationError
if release.version_info[0] >= 19:
    from odoo.models import Constraint

from odoo.addons.connect.models.settings import debug
from .settings import format_connect_response

logger = logging.getLogger(__name__)


class TelnyxRcsAgent(models.Model):
    """RCS agents provisioned in the Telnyx account (ADR-033).

    Agents are onboarded through Telnyx/Google RBM — Odoo only syncs
    them and sends messages on their behalf.
    """
    _name = 'connect.telnyx.rcs_agent'
    _description = 'Telnyx RCS Agent'
    _rec_name = 'agent_name'
    _order = 'agent_name'

    agent_id = fields.Char(string='Agent ID', required=True, readonly=True, index=True)
    agent_name = fields.Char(string='Name', readonly=True)
    enabled = fields.Boolean(readonly=True)
    profile_id = fields.Char(string='Messaging Profile ID', readonly=True)
    is_default = fields.Boolean(string='Default RCS Agent')

    if release.version_info[0] >= 19:
        _agent_id_unique = Constraint('UNIQUE(agent_id)', 'This RCS agent already exists!')
    else:
        _sql_constraints = [
            ('agent_id_unique', 'UNIQUE(agent_id)', 'This RCS agent already exists!'),
        ]

    @api.constrains('is_default')
    def _check_single_default(self):
        for rec in self:
            if rec.is_default:
                others = self.search([('is_default', '=', True), ('id', '!=', rec.id)], limit=1)
                if others:
                    raise ValidationError('Only one RCS agent can be marked as default.')

    @api.model
    def sync(self):
        client = self.env['connect.settings'].get_telnyx_client()
        try:
            items = list(client.messaging.rcs.agents.list())
        except Exception as e:
            raise ValidationError("Failed to sync RCS agents: {}".format(
                format_connect_response(e)))
        seen = set()
        for item in items:
            if not item.agent_id:
                continue
            seen.add(item.agent_id)
            vals = {
                'agent_id': item.agent_id,
                'agent_name': item.agent_name,
                'enabled': bool(item.enabled),
                'profile_id': item.profile_id,
            }
            rec = self.search([('agent_id', '=', item.agent_id)], limit=1)
            if rec:
                rec.write(vals)
            else:
                self.create([vals])
                debug(self, 'Created RCS agent {}'.format(item.agent_id))
        missing = self.search([('agent_id', 'not in', list(seen))]) if seen \
            else self.search([])
        if missing:
            debug(self, 'Removing missing RCS agents: {}'.format(
                ', '.join(missing.mapped('agent_id'))))
            missing.unlink()

    def action_sync(self):
        self.sync()
        return True

    @api.model
    def get_default_agent(self):
        default = self.search([('is_default', '=', True)], limit=1)
        if default:
            return default
        return self.search([('enabled', '=', True)], limit=1) or self.search([], limit=1)

    def send_rcs(self, recipient, body, res_model=None, res_id=None,
                 raise_on_error=True, sms_fallback_from=None):
        """Send an RCS text message (with optional SMS fallback) and
        create connect.message + chatter.

        Args:
            recipient (str): E.164 phone.
            body (str): Message text.
            res_model / res_id: Optional record to post to chatter.
            raise_on_error (bool): Raise ValidationError on failures.
            sms_fallback_from (str): E.164 sender for the SMS fallback;
                no fallback is requested when empty.
        """
        self.ensure_one()
        self.env['oduist.license'].check_license('connect', silent=False)
        profile_id = self.profile_id or self.env['connect.settings'].sudo().get_param(
            'telnyx_messaging_profile_id')
        if not profile_id:
            raise ValidationError(
                'No messaging profile available for RCS. Run the Telnyx sync first.')
        client = self.env['connect.settings'].get_telnyx_client()
        kwargs = {
            'agent_id': self.agent_id,
            'to': recipient,
            'messaging_profile_id': profile_id,
            'agent_message': {
                'content_message': {'text': body or ''},
            },
            'type': 'RCS',
        }
        if sms_fallback_from:
            kwargs['sms_fallback'] = {
                'from': sms_fallback_from,
                'text': body or '',
            }
        try:
            response = client.messages.rcs.send(**kwargs)
            message = response.data
        except Exception as e:
            if raise_on_error:
                raise ValidationError('Unable to send RCS message: {}'.format(
                    format_connect_response(e)))
            logger.error('Unable to send RCS message to %s via %s: %s',
                         recipient, self.agent_id, e)
            return False
        message_sid = getattr(message, 'id', None) if message else None
        if not message_sid:
            if raise_on_error:
                raise ValidationError('RCS API did not return a message ID.')
            logger.error('RCS API did not return a message ID for recipient %s', recipient)
            return False

        sender_user = self.env.user
        partner = self.env['res.partner'].get_partner_by_number(recipient)
        msg_vals = {
            'message_type': 'RCS',
            'to_number': recipient,
            'from_number': sms_fallback_from or self.agent_id,
            'body': body,
            'sender_user': sender_user.id,
            'partner': partner.id if partner else False,
            'res_model': res_model,
            'res_id': res_id,
            'status': 'sent',
            'message_sid': message_sid,
        }
        msg = self.env['connect.message'].sudo().create(msg_vals)

        if res_model and res_id:
            chatter_message = Markup(f"<div class='d-flex flex-row'>"
                                     f"<p class='px-1'>{body}</p></div>")
            self.chatter_post(res_model, res_id, self.env.user.partner_id.id, chatter_message)
        return msg

    def chatter_post(self, res_model, res_id, author, body):
        try:
            mt_note = self.env.ref('mail.mt_note').id
            obj = self.env[res_model].browse(res_id)
            if hasattr(obj, 'message_post'):
                chatter = obj.sudo().with_context(mail_create_nosubscribe=True).message_post(
                    body=body,
                    subtype_id=mt_note,
                    message_type='RCS',
                    author_id=author,
                )
                self.env['mail.notification'].sudo().create([{
                    'author_id': chatter.author_id.id,
                    'mail_message_id': chatter.id,
                    'res_partner_id': chatter.author_id.id,
                    'sms_number': self.agent_id,
                    'notification_type': 'RCS',
                    'is_read': True,
                    'notification_status': 'ready',
                }])
                self.env['connect.settings'].connect_reload_view(res_model)
        except Exception as e:
            logger.warning('Failed to post RCS chatter message on %s,%s: %s', res_model, res_id, e)
