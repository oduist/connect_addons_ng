import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)


class HelpdeskCall(models.Model):
    _inherit = 'connect.call'

    ticket = fields.Many2one(
        'helpdesk.ticket', ondelete='set null', tracking=True,
    )
    ref = fields.Reference(selection_add=[('helpdesk.ticket', 'Ticket')])

    def _get_ref(self):
        for rec in self:
            if rec.ticket:
                rec.ref = 'helpdesk.ticket,{}'.format(rec.ticket.id)
            else:
                super(HelpdeskCall, rec)._get_ref()

    @api.model
    def process_call_event(self, channel, error_data=None):
        call_id = super().process_call_event(channel, error_data=error_data)
        if not call_id:
            return call_id
        if not self.env['oduist.license'].check_license(
            'connect_helpdesk', silent=True,
        ):
            return call_id
        call = self.browse(call_id)
        try:
            if not call.ticket:
                if call.direction == 'incoming':
                    ticket = self.env['helpdesk.ticket'].get_ticket_by_number(
                        call.caller,
                    )
                else:
                    ticket = self.env['helpdesk.ticket'].get_ticket_by_number(
                        call.called,
                    )
                if ticket:
                    debug(self, 'Call {} assign <{}> "{}"'.format(
                        call.id, ticket.id, ticket.name,
                    ))
                    call.ticket = ticket
        except Exception:
            logger.exception('Helpdesk process_call_event error:')
        return call_id

    def register_call(self, channel, params):
        res = super().register_call(channel, params)
        if not self.env['oduist.license'].check_license(
            'connect_helpdesk', silent=True,
        ):
            return res
        try:
            channel.call.sudo()._auto_create_ticket()
        except Exception:
            logger.exception('Auto create ticket error (handled):')
        return res

    def _auto_create_ticket(self):
        self.ensure_one()
        if self.ticket:
            debug(self, '{} ticket already set: {}'.format(self.id, self.ticket))
            return False
        if not self.direction:
            debug(self, 'Call direction undefined for: {}'.format(self.id))
            return False
        Settings = self.env['connect.settings']
        in_calls = Settings.get_param('auto_create_tickets_for_in_calls')
        in_answered = Settings.get_param('auto_create_tickets_for_in_answered_calls')
        in_missed = Settings.get_param('auto_create_tickets_for_in_missed_calls')
        in_unknown = Settings.get_param('auto_create_tickets_for_in_unknown_callers')
        out_calls = Settings.get_param('auto_create_tickets_for_out_calls')
        out_answered = Settings.get_param('auto_create_tickets_for_out_answered_calls')
        out_missed = Settings.get_param('auto_create_tickets_for_out_missed_calls')
        default_team = Settings.get_param('auto_create_tickets_team')
        default_user = Settings.get_param('auto_create_tickets_user')
        data = {}
        if self.direction == 'incoming':
            if not in_calls:
                debug(self, 'Autocreate not enabled for incoming calls')
                return False
            if self.status == 'completed' and in_answered:
                debug(self, 'Creating a ticket for answered incoming call.')
            elif self.status != 'completed' and in_missed:
                debug(self, 'Creating a ticket for missed incoming call.')
            elif not self.partner and in_unknown:
                debug(self, 'Creating a ticket for unknown incoming caller.')
            else:
                debug(self, 'No helpdesk call auto create rule matched for {}'.format(self.id))
                return False
            user_id = self.answered_pbx_user.user.id or (
                self.called_pbx_users and self.called_pbx_users[:1].user.id
            )
            if not user_id:
                user_id = default_user.id if default_user else False
            data = {
                'name': self.partner.name or self.caller,
                'partner_id': self.partner.id,
                'user_id': user_id,
            }
            if not self.partner:
                data['partner_phone'] = self.caller
        elif self.direction == 'outgoing':
            if not out_calls:
                debug(self, 'Autocreate not enabled for outgoing calls')
                return False
            if self.called_pbx_users:
                debug(self, 'Autocreate skip "out" call to local users')
                return False
            if self.status == 'completed' and out_answered:
                debug(self, 'Creating a ticket for answered outgoing call.')
            elif self.status != 'completed' and out_missed:
                debug(self, 'Creating a ticket for missed outgoing call.')
            else:
                debug(self, 'No outgoing rule matched for {}'.format(self.id))
                return False
            user_id = self.caller_user.id or (
                default_user.id if default_user else False
            )
            data = {
                'name': self.partner.name or self.called,
                'partner_id': self.partner.id,
                'user_id': user_id,
            }
            if not self.partner:
                data['partner_phone'] = self.called
        if data:
            if default_team:
                data['team_id'] = default_team.id
            debug(self, 'Ticket create data: {}'.format(data))
            ticket = self.env['helpdesk.ticket'].create(data)
            debug(self, 'Set ticket {} for call {}'.format(ticket.id, self.id))
            self.ticket = ticket
            return True
        return False

    def create_ticket_button(self):
        self.ensure_one()
        if not self.env['oduist.license'].check_license(
            'connect_helpdesk', silent=True,
        ):
            raise ValidationError('Connect Helpdesk license is not activated!')
        name_number = self.caller if self.direction == 'incoming' else self.called
        context = {
            'connect_call_id': self.id,
            'default_partner_phone': name_number,
            'default_partner_id': self.partner.id,
        }
        if not self.ticket:
            ticket = self.env['helpdesk.ticket'].get_ticket_by_number(name_number)
            if ticket:
                self.sudo().ticket = ticket
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'helpdesk.ticket',
            'res_id': self.ticket.id,
            'name': self.ticket.name if self.ticket else 'New ticket',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def unlink_ticket(self):
        self.ensure_one()
        self.ticket = False

    def get_widget_fields(self):
        fields = super().get_widget_fields()
        fields.append('ticket')
        return fields

    @api.constrains('summary')
    def register_helpdesk_ticket_call_summary(self):
        if not self.env['oduist.license'].check_license(
            'connect_helpdesk', silent=True,
        ):
            return False
        register_summary = self.env['connect.settings'].sudo().get_param(
            'register_summary',
        )
        if not register_summary:
            return
        reload_view = False
        for rec in self:
            if rec.ticket and rec.summary:
                self.register_summary_to_rec(rec.ticket, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('helpdesk.ticket')
