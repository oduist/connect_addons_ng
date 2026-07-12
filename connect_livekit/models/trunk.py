# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from livekit import api as lk_api

from odoo.addons.connect.models.settings import debug

logger = logging.getLogger(__name__)

SIP_TRANSPORTS = {
    'udp': lk_api.SIPTransport.SIP_TRANSPORT_UDP,
    'tcp': lk_api.SIPTransport.SIP_TRANSPORT_TCP,
    'tls': lk_api.SIPTransport.SIP_TRANSPORT_TLS,
}


class LivekitTrunk(models.Model):
    """A BYO carrier SIP trunk registered on the LiveKit SIP bridge.

    Odoo is the source of truth (ADR-036): saving pushes the trunk to
    LiveKit (delete + create — trunk updates re-issue the sid, and the
    numbers re-push their dispatch rules right after in sync()).
    """
    _name = 'connect.livekit.trunk'
    _description = 'LiveKit SIP Trunk'
    _order = 'id'

    name = fields.Char(required=True)
    # Inbound: calls arriving from the carrier.
    inbound_trunk_sid = fields.Char(readonly=True, copy=False)
    inbound_addresses = fields.Char(
        string='Inbound Addresses',
        help="Comma-separated carrier signaling IPs/CIDRs allowed to send "
             "calls (leave empty to accept by number match only).")
    inbound_auth_username = fields.Char()
    inbound_auth_password = fields.Char(
        groups="connect.group_admin,base.group_erp_manager")
    krisp_enabled = fields.Boolean(
        string='Krisp Noise Cancellation',
        help="Enable Krisp on inbound SIP participants (LiveKit Cloud "
             "feature; ignored on plain self-hosted servers).")
    # Outbound: calls placed through the carrier.
    outbound_trunk_sid = fields.Char(readonly=True, copy=False)
    outbound_address = fields.Char(
        string='Outbound Address',
        help="Carrier SIP host, e.g. sip.telnyx.com.")
    outbound_transport = fields.Selection([
        ('udp', 'UDP'),
        ('tcp', 'TCP'),
        ('tls', 'TLS'),
    ], default='udp', required=True)
    outbound_auth_username = fields.Char()
    outbound_auth_password = fields.Char(
        groups="connect.group_admin,base.group_erp_manager")

    def _inbound_numbers(self):
        self.ensure_one()
        return self.env['connect.livekit.number'].sudo().search(
            [('trunk', '=', self.id)]).mapped('phone_number')

    def _outbound_numbers(self):
        self.ensure_one()
        return self.env['connect.livekit.outgoing_callerid'].sudo().search(
            [('trunk', '=', self.id)]).mapped('number')

    def _delete_remote_trunk(self, sid):
        if not sid:
            return
        try:
            self.env['connect.settings'].livekit_api_call(
                'sip.delete_sip_trunk',
                lk_api.DeleteSIPTrunkRequest(sip_trunk_id=sid))
        except ValidationError as e:
            # Already gone on the server: recreate cleanly.
            logger.warning('LiveKit delete trunk %s: %s', sid, e)

    def _push_inbound(self):
        for rec in self:
            rec._delete_remote_trunk(rec.inbound_trunk_sid)
            addresses = [
                a.strip() for a in (rec.inbound_addresses or '').split(',')
                if a.strip()]
            info = lk_api.SIPInboundTrunkInfo(
                name=rec.name,
                numbers=rec._inbound_numbers(),
                allowed_addresses=addresses,
                auth_username=rec.sudo().inbound_auth_username or '',
                auth_password=rec.sudo().inbound_auth_password or '',
                krisp_enabled=rec.krisp_enabled,
            )
            resp = self.env['connect.settings'].livekit_api_call(
                'sip.create_inbound_trunk',
                lk_api.CreateSIPInboundTrunkRequest(trunk=info))
            rec.with_context(skip_livekit_sync=True).write(
                {'inbound_trunk_sid': resp.sip_trunk_id})
            debug(self, 'LiveKit inbound trunk {} pushed as {}.'.format(
                rec.name, resp.sip_trunk_id))

    def _push_outbound(self):
        for rec in self:
            numbers = rec._outbound_numbers()
            # LiveKit rejects outbound trunks without numbers
            # ("no trunk numbers specified") — wait for the first
            # outgoing caller ID; its create/write re-pushes the trunk.
            if not rec.outbound_address or not numbers:
                debug(self, 'LiveKit outbound trunk {} not pushed: address '
                            'or caller IDs missing.'.format(rec.name))
                continue
            rec._delete_remote_trunk(rec.outbound_trunk_sid)
            info = lk_api.SIPOutboundTrunkInfo(
                name=rec.name,
                address=rec.outbound_address,
                transport=SIP_TRANSPORTS[rec.outbound_transport or 'udp'],
                numbers=numbers,
                auth_username=rec.sudo().outbound_auth_username or '',
                auth_password=rec.sudo().outbound_auth_password or '',
            )
            resp = self.env['connect.settings'].livekit_api_call(
                'sip.create_outbound_trunk',
                lk_api.CreateSIPOutboundTrunkRequest(trunk=info))
            rec.with_context(skip_livekit_sync=True).write(
                {'outbound_trunk_sid': resp.sip_trunk_id})
            debug(self, 'LiveKit outbound trunk {} pushed as {}.'.format(
                rec.name, resp.sip_trunk_id))

    @api.model
    def sync(self):
        trunks = self.search([])
        trunks._push_inbound()
        trunks._push_outbound()
        # Dispatch rules reference the (re-issued) inbound trunk sids.
        self.env['connect.livekit.number'].sync()

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if (self.env['connect.settings'].sudo().get_param('livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            recs._push_inbound()
            recs._push_outbound()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if (self.env['connect.settings'].sudo().get_param('livekit_auto_sync')
                and not self.env.context.get('skip_livekit_sync')):
            self._push_inbound()
            self._push_outbound()
            self.env['connect.livekit.number'].search(
                [('trunk', 'in', self.ids)])._push_dispatch_rule()
        return res

    def unlink(self):
        for rec in self:
            rec._delete_remote_trunk(rec.inbound_trunk_sid)
            rec._delete_remote_trunk(rec.outbound_trunk_sid)
        return super().unlink()
