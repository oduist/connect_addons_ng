# -*- coding: utf-8 -*-
import json
import logging
import secrets
import uuid
from urllib.parse import urljoin

from odoo import api, fields, models, release
if release.version_info[0] >= 19:
    from odoo.models import Constraint
from odoo.exceptions import ValidationError

from livekit import api as lk_api

logger = logging.getLogger(__name__)


class LivekitRoom(models.Model):
    _name = 'connect.livekit.room'
    _description = 'LiveKit Room'
    _inherit = ['mail.thread']
    _rec_name = 'name'
    _order = 'id desc'

    name = fields.Char(required=True)
    # LiveKit room name; the meet- prefix drives the ledger mapping (ADR-036).
    room_name = fields.Char(readonly=True, copy=False, index=True)
    sid = fields.Char('SID', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('finished', 'Finished'),
    ], default='draft', tracking=True)
    user = fields.Many2one(
        'res.users', string='Organizer',
        default=lambda self: self.env.user)
    partner = fields.Many2one('res.partner', ondelete='set null')
    # Guests authenticate purely by this unguessable URL token.
    guest_token = fields.Char(readonly=True, copy=False, groups="connect.group_admin")
    public_url = fields.Char(compute='_get_public_url')
    record = fields.Boolean(string='Record Meeting')
    egress_sid = fields.Char(readonly=True, copy=False)
    empty_timeout = fields.Integer(
        default=300,
        help="Seconds the LiveKit room stays open with no participants.")
    max_participants = fields.Integer(default=10)
    call = fields.Many2one('connect.call', readonly=True, ondelete='set null')

    if release.version_info[0] >= 19:
        _room_name_uniq = Constraint(
            'UNIQUE(room_name)', 'Room name must be unique!')
        _guest_token_uniq = Constraint(
            'UNIQUE(guest_token)', 'Guest token must be unique!')
    else:
        _sql_constraints = [
            ('room_name_uniq', 'UNIQUE(room_name)',
             'Room name must be unique!'),
            ('guest_token_uniq', 'UNIQUE(guest_token)',
             'Guest token must be unique!'),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault(
                'room_name', 'meet-{}'.format(uuid.uuid4().hex[:8]))
            vals.setdefault('guest_token', secrets.token_urlsafe(16))
        return super().create(vals_list)

    def _get_public_url(self):
        api_url = self.env['connect.settings'].sudo().get_param('api_url')
        for rec in self:
            rec.public_url = urljoin(
                api_url or '', '/livekit/meet/{}'.format(
                    rec.sudo().guest_token))

    def _ensure_livekit_room(self):
        """Create the room on the LiveKit server (idempotent by name)."""
        self.ensure_one()
        room = self.env['connect.settings'].livekit_api_call(
            'room.create_room',
            lk_api.CreateRoomRequest(
                name=self.room_name,
                empty_timeout=self.empty_timeout or 300,
                max_participants=self.max_participants or 0,
                metadata=json.dumps({'room_id': self.id}),
            ))
        vals = {}
        if not self.sid and getattr(room, 'sid', None):
            vals['sid'] = room.sid
        if self.state == 'draft':
            vals['state'] = 'active'
        if vals:
            self.sudo().write(vals)
        return room

    def action_join(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.public_url,
            'target': 'new',
        }

    def action_start_recording(self):
        self.ensure_one()
        if self.egress_sid:
            raise ValidationError('Recording is already running!')
        if self.state != 'active':
            self._ensure_livekit_room()
        # Audio-only OGG by default: the recording feeds the transcription
        # pipeline; video composites can be added later.
        info = self.env['connect.settings'].livekit_api_call(
            'egress.start_room_composite_egress',
            lk_api.RoomCompositeEgressRequest(
                room_name=self.room_name,
                audio_only=True,
                file_outputs=[lk_api.EncodedFileOutput(
                    file_type=lk_api.EncodedFileType.OGG,
                    filepath='{room_name}-{time}',
                )],
            ))
        self.write({'egress_sid': info.egress_id, 'record': True})

    def action_stop_recording(self):
        self.ensure_one()
        if not self.egress_sid:
            raise ValidationError('No recording is running!')
        self.env['connect.settings'].livekit_api_call(
            'egress.stop_egress',
            lk_api.StopEgressRequest(egress_id=self.egress_sid))
        self.egress_sid = False

    def action_close(self):
        self.ensure_one()
        try:
            self.env['connect.settings'].livekit_api_call(
                'room.delete_room',
                lk_api.DeleteRoomRequest(room=self.room_name))
        except ValidationError as e:
            # The room may have expired on the server already.
            logger.warning('LiveKit delete_room %s: %s', self.room_name, e)
        self.write({'state': 'finished', 'egress_sid': False})

    @api.model
    def get_room_by_guest_token(self, guest_token):
        """Resolve a meet link. Called with sudo from the public controller."""
        if not guest_token:
            return self.browse()
        return self.sudo().search(
            [('guest_token', '=', guest_token),
             ('state', '!=', 'finished')], limit=1)
