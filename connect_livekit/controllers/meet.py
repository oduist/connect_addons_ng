# -*- coding: utf-8 -*-
"""Public meeting page.

Guests authenticate purely by the unguessable guest_token in the URL
(ADR-037); logged-in internal users join under their real identity so
their ledger channels resolve to connect.user.
"""
import json
import logging
import secrets

from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound

logger = logging.getLogger(__name__)


class LivekitMeetController(http.Controller):

    @staticmethod
    def _get_room(guest_token):
        return request.env['connect.livekit.room'].sudo(
        ).get_room_by_guest_token(guest_token)

    @http.route('/livekit/meet/<string:guest_token>', methods=['GET'],
                type='http', auth='public', csrf=False)
    def meet_page(self, guest_token, **kw):
        room = self._get_room(guest_token)
        if not room:
            raise NotFound()
        return request.render('connect_livekit.meet_page', {
            'room_title': room.name,
            'guest_token': guest_token,
        })

    @http.route('/livekit/meet/<string:guest_token>/join',
                methods=['POST'], type='http', auth='public', csrf=False)
    def meet_join(self, guest_token, **kw):
        room = self._get_room(guest_token)
        if not room:
            return request.make_json_response(
                {'error': 'not found'}, status=404)
        try:
            payload = json.loads(
                request.httprequest.get_data(as_text=True) or '{}')
        except ValueError:
            payload = {}
        display_name = (payload.get('display_name') or '').strip()[:64]
        settings = request.env['connect.settings'].sudo()
        user = request.env.user
        if not user._is_public() and user.connect_user:
            identity = 'user-{}'.format(user.connect_user.id)
            display_name = display_name or user.name
        else:
            identity = 'guest-{}'.format(secrets.token_hex(4))
            display_name = display_name or 'Guest'
        room._ensure_livekit_room()
        if room.record and not room.egress_sid:
            try:
                room.action_start_recording()
            except Exception as e:
                # Recording must not block joining the meeting.
                logger.error('LiveKit auto-record failed for %s: %s',
                             room.room_name, e)
        token = settings.livekit_create_token(
            identity=identity, name=display_name,
            room_name=room.room_name, ttl=3600)
        return request.make_json_response({
            'token': token,
            'ws_url': settings.get_param('livekit_ws_url'),
            'room_name': room.room_name,
            'display_name': display_name,
        })
