# -*- coding: utf-8 -*-
"""HTTP controllers for the agent → Odoo direction.

The sidecar agent (oduist/asterisk-agent) POSTs batches of filtered AMI
events, uploads finished recordings and reports heartbeats. Every request
must carry ``Authorization: Bearer <asterisk_agent_token>``.

Unlike the firewall controllers (bare ``sudo()``), event and recording
processing dispatches under the core webhook user
(``connect.user_connect_webhook``): the target models already carry
webhook-group ACLs in core, which bounds the blast radius of a leaked
token. See specs/decisions/025-asterisk-sidecar-agent.md.
"""
import base64
import json
import logging
import secrets

from odoo import fields, http
from odoo.http import Response, request

logger = logging.getLogger(__name__)

# AMI event name → connect.channel handler. Guard conditions that the
# legacy asterisk_plus.event registry expressed as code strings live in
# the handlers themselves (Local/ filter, Newstate Up, VarSet variable).
EVENT_HANDLERS = {
    'Newchannel': 'on_ami_new_channel',
    'Newstate': 'on_ami_new_state',
    'NewConnectedLine': 'on_ami_new_connected_line',
    'Hangup': 'on_ami_hangup',
    'OriginateResponse': 'on_ami_originate_response_failure',
    'VarSet': 'on_ami_var_set',
}


class AsteriskWebhooksController(http.Controller):

    @staticmethod
    def _check_token():
        expected = request.env['connect.settings'].sudo().get_param(
            'asterisk_agent_token'
        ) or ''
        if not expected:
            return False
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.lower().startswith('bearer '):
            return False
        return secrets.compare_digest(auth[7:].strip(), expected)

    @staticmethod
    def _json(payload, status=200):
        return Response(
            json.dumps(payload, default=str),
            status=status,
            content_type='application/json',
        )

    @classmethod
    def _unauthorized(cls):
        return Response(
            json.dumps({'error': 'unauthorized'}),
            status=401,
            content_type='application/json',
            headers=[('WWW-Authenticate', 'Bearer')],
        )

    @staticmethod
    def _read_payload():
        raw = request.httprequest.get_data(as_text=True) or ''
        if not raw:
            return {}
        return json.loads(raw)

    @http.route('/asterisk/webhook/events',
                type='http', auth='none', methods=['POST'], csrf=False,
                readonly=False)
    def events(self, **_):
        """Batch of AMI events from the agent: JSON array of event dicts
        with original AMI field names (Event, Uniqueid, Linkedid, ...)."""
        if not self._check_token():
            return self._unauthorized()
        try:
            payload = self._read_payload()
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return self._json({'error': 'bad_payload'}, status=400)
        webhook_user = request.env.ref('connect.user_connect_webhook')
        Channel = request.env['connect.channel'].with_user(webhook_user.id)
        processed = 0
        for event in payload:
            if not isinstance(event, dict):
                continue
            handler = EVENT_HANDLERS.get(event.get('Event'))
            if not handler:
                continue
            try:
                getattr(Channel, handler)(event)
                processed += 1
            except Exception:
                logger.exception('Error processing AMI event %s (%s):',
                                 event.get('Event'), event.get('Uniqueid'))
        return self._json({'ok': True, 'processed': processed})

    @http.route('/asterisk/webhook/recording/<string:filename>',
                type='http', auth='none', methods=['PUT', 'POST'], csrf=False,
                readonly=False)
    def recording(self, filename, **_):
        """Receive a recording file from the agent.

        The filename is expected to be <uniqueid>.<ext> where uniqueid is
        the AMI Uniqueid (channel SID in Odoo). The upload may arrive
        before or after the Hangup event — both orders are safe: the
        Hangup handler links orphan recordings, and this handler links
        the channel when it already exists.
        """
        if not self._check_token():
            return self._unauthorized()
        uniqueid = filename.rsplit('.', 1)[0] if '.' in filename else filename
        if not uniqueid:
            return Response('No UID', status=400)
        file_data = request.httprequest.get_data()
        if not file_data:
            return Response('No file data', status=400)
        try:
            webhook_user = request.env.ref('connect.user_connect_webhook')
            Recording = request.env['connect.recording'].with_user(
                webhook_user.id)
            existing = Recording.sudo().search(
                [('call_sid', '=', uniqueid)], limit=1)
            if existing:
                logger.info(
                    'Recording for %s already exists (id=%s), skipping.',
                    uniqueid, existing.id)
                return Response('OK', status=200)
            channel = request.env['connect.channel'].sudo().search(
                [('sid', '=', uniqueid)], limit=1)
            vals = {
                'call_sid': uniqueid,
                'status': 'completed',
                'source': 'asterisk',
                'recording_attachment': base64.b64encode(file_data),
                'recording_filename': filename,
            }
            if channel:
                vals.update({
                    'call': channel.call.id if channel.call else False,
                    'channel': channel.id,
                    'partner': channel.partner.id if channel.partner else False,
                    'duration': channel.duration,
                    'caller_number': channel.caller_number,
                    'called_number': channel.called_number,
                })
            recording = Recording.sudo().create(vals)
            logger.info(
                'Recording created: id=%s, uid=%s, channel=%s, %d bytes',
                recording.id, uniqueid,
                channel.id if channel else 'pending', len(file_data))
        except Exception as e:
            logger.exception('Failed to process recording for %s: %s',
                             uniqueid, e)
            return Response('Processing error', status=500)
        return Response('OK', status=200)

    @http.route('/asterisk/webhook/heartbeat',
                type='http', auth='none', methods=['POST'], csrf=False,
                readonly=False)
    def heartbeat(self, **_):
        if not self._check_token():
            return self._unauthorized()
        try:
            payload = self._read_payload()
        except ValueError:
            return self._json({'error': 'bad_json'}, status=400)
        settings = request.env['connect.settings'].sudo()
        ami_ok = payload.get('ami_connected')
        settings.set_param(
            'asterisk_agent_status',
            'UP — AMI {}'.format('connected' if ami_ok else 'DISCONNECTED'))
        settings.set_param(
            'asterisk_agent_version', payload.get('version') or '')
        settings.set_param('asterisk_last_heartbeat', fields.Datetime.now())
        return self._json({'ok': True})
