# -*- coding: utf-8 -*-
import json
import logging
from urllib.parse import urlencode, urlsplit, urlunsplit

from markupsafe import escape

from odoo import models, api, release
from odoo.exceptions import UserError

from .voiceml_response import VoiceResponse

from odoo.addons.connect.models.channel import CALL_END_STATUSES
from odoo.addons.connect.models.settings import debug
from voiceml.models import (
    StartRecordingRequest, UpdateCallRequest, UpdateRecordingRequest)

from .settings import MAX_EXTEN_LEN

logger = logging.getLogger(__name__)

# Recording statuses that mean "audio is still being captured". VoiceTel's
# terminal states are 'completed', 'absent', 'deleted' and 'stopped'; a
# running recording shows up as 'processing' (or 'in-progress'/'paused'
# depending on how it was started), so all three count as live.
VOICETEL_LIVE_RECORDING_STATUSES = ('in-progress', 'processing', 'paused')


class Channel(models.Model):
    _inherit = 'connect.channel'

    @api.model
    def on_voicetel_call_status(self, params):
        """VoiceML webhook adapter: map the Twilio-shaped params and delegate to core."""
        debug(self, 'On channel status: %s' % json.dumps(params, indent=2))
        generic = self._map_voicetel_params(params)
        return self.process_channel_event(generic)

    def _strip_exten_plus(self, number):
        """Undo the E.164 prefix VoiceTel puts on an extension used as caller ID.

        Internal calls hand VoiceTel a bare extension (``100``) as the caller
        ID, and VoiceTel echoes it back in its webhooks as ``+100``. Map it back
        to the extension so the ledger shows ``100`` instead of a bogus
        phone number.
        """
        if not isinstance(number, str) or not number.startswith('+'):
            return number
        candidate = number[1:]
        if not candidate.isdigit() or len(candidate) > MAX_EXTEN_LEN:
            return number
        exten = self.env['connect.voicetel.exten'].sudo().search(
            [('number', '=', candidate)], limit=1
        )
        return candidate if exten else number

    def _map_voicetel_params(self, params):
        """Map the Twilio-shaped VoiceML webhook params to the generic channel event dict."""
        return {
            'sid': params['CallSid'],
            'caller': self._strip_exten_plus(params.get('Caller')),
            'called': self._strip_exten_plus(params.get('Called')),
            'to': params.get('To'),
            'technical_direction': params.get('Direction'),
            'status': params.get('CallStatus'),
            'duration': int(params.get('CallDuration') or 0),
            'call_type': 'phone',
            'parent_sid': params.get('ParentCallSid'),
        }

    def _voicetel_recording_call_sids(self):
        """Call SIDs that may carry a recording for this channel.

        A callflow records on the leg that runs ``<Dial record=...>`` — the
        parent — while manual softphone recording is created on this leg, so
        both have to be considered before reporting a state.
        """
        self.ensure_one()
        sids = []
        channel = self
        while channel:
            if channel.sid and channel.sid not in sids:
                sids.append(channel.sid)
            parent = channel.parent_channel
            if not parent and channel.parent_sid:
                parent = self.sudo().search(
                    [('sid', '=', channel.parent_sid)], limit=1)
            if not parent or parent.sid in sids:
                break
            channel = parent
        return sids

    def _voicetel_active_recording(self):
        """Return ``(call_sid, recording_sid)`` of a recording running now.

        VoiceTel is the only authority on this: recording may have been started
        by a callflow, by the per-user Record Calls option or manually from
        the softphone, and only the API knows which of them is live.
        """
        self.ensure_one()
        try:
            client = self.env['connect.settings'].sudo().get_voicetel_client()
        except Exception:
            logger.exception('VoiceTel client unavailable for %s', self.sid)
            return '', ''
        for call_sid in self._voicetel_recording_call_sids():
            try:
                # CallRecordingList.list() filters by date only. Asking it for
                # status='in-progress' raises TypeError, and the except below
                # swallowed it -- so a recording running on the call was never
                # seen and the softphone button stayed idle through a call the
                # Record Calls option was recording.
                # ...and matching only 'in-progress' was still wrong: VoiceTel
                # reports a recording that is still running as 'processing'
                # (duration -1). Measured on a live call — recording
                # RE4df4b06d on an in-progress call came back 'processing',
                # and across 50 recordings on the account only 'processing'
                # (live) and 'completed' (finished) ever appeared, so the
                # 'in-progress' test never matched and the button stayed on
                # "Start Recording" for the whole call.
                recordings = [
                    recording
                    for recording in client.calls.list_recordings(
                        call_sid, page_size=20).recordings
                    if getattr(recording, 'status', '')
                    in VOICETEL_LIVE_RECORDING_STATUSES
                ]
            except Exception:
                logger.exception(
                    'VoiceTel recording lookup failed for %s', call_sid)
                continue
            if recordings:
                return call_sid, getattr(recordings[0], 'sid', '') or ''
        return '', ''

    @api.model
    def _softphone_recording_state_voicetel(self, payload):
        channel = self._softphone_recording_channel(payload)
        result = channel._softphone_recording_payload()
        if result['state'] in ('off', '') and not result['recording_ref']:
            call_sid, recording_sid = channel._voicetel_active_recording()
            if call_sid:
                result['state'] = 'on'
                result['recording_ref'] = recording_sid
        return result

    @api.model
    def _softphone_recording_start_voicetel(self, payload):
        channel = self._softphone_recording_channel(payload)
        channel._check_softphone_recording_active()
        channel.sudo().write({
            'recording_state': 'starting',
            'recording_control_error': False,
        })
        try:
            settings = self.env['connect.settings'].sudo()
            api_url = settings.get_param('api_url')
            callback_url = settings.voicetel_webhook_url(
                'voicetel/webhook/recordingstatus')
            kwargs = {
                'RecordingChannels': 'dual',
            }
            if api_url:
                kwargs.update({
                    'RecordingStatusCallback': callback_url,
                    'RecordingStatusCallbackEvent': ['completed'],
                })
            recording = settings.get_voicetel_client().calls(
                channel.sid).recordings.create(**kwargs)
            channel.sudo().write({
                'recording_state': 'on',
                'recording_control_ref': getattr(recording, 'sid', '') or '',
                'recording_control_error': False,
            })
        except Exception as e:
            logger.exception('VoiceTel recording start failed for %s', channel.sid)
            channel.sudo().write({
                'recording_state': 'error',
                'recording_control_error': str(e),
            })
            raise UserError('Could not start recording: {}'.format(e))
        return channel._softphone_recording_payload()

    @api.model
    def _softphone_recording_stop_voicetel(self, payload):
        channel = self._softphone_recording_channel(payload)
        channel._check_softphone_recording_active()
        channel.sudo().write({
            'recording_state': 'stopping',
            'recording_control_error': False,
        })
        call_sid, recording_ref = channel._voicetel_active_recording()
        if not call_sid:
            call_sid = channel.sid
            # 'Twilio.CURRENT' is the literal alias VoiceML's Recordings update
            # accepts for the active recording (its Twilio-compat wire value).
            recording_ref = channel.recording_control_ref or 'Twilio.CURRENT'
        try:
            self.env['connect.settings'].sudo().get_voicetel_client().calls.update_recording(
                call_sid, recording_ref, UpdateRecordingRequest(Status='stopped'))
            channel.sudo().write({
                'recording_state': 'off',
                'recording_control_ref': 'manual-off',
                'recording_control_error': False,
            })
        except Exception as e:
            logger.exception('VoiceTel recording stop failed for %s', channel.sid)
            channel.sudo().write({
                'recording_state': 'error',
                'recording_control_error': str(e),
            })
            raise UserError('Could not stop recording: {}'.format(e))
        return channel._softphone_recording_payload()

    def _softphone_forward_voicetel(self, payload):
        """Blind-transfer the call this softphone leg belongs to.

        The other party's leg is pointed back at the same VoiceML application
        that routes every outgoing call, with the destination carried in
        `forward_to`. Routing is therefore not reimplemented here: an
        extension resolves to the colleague's client or SIP phone and an
        external number is dialled with the usual caller ID, because
        `connect.voicetel.domain.route_call()` does the deciding either way.

        Redirecting the *other* leg is what makes this work in both
        directions. On an inbound call that leg is the customer; on an
        outbound one it is the person we called. Either way it is the party
        who should end up talking to the forward target, and our own leg drops
        as soon as the bridge goes away.
        """
        channel = self._softphone_recording_channel(payload)
        # Same resolution and ownership checks the recording controls use:
        # the helper answers "which live leg is this softphone on, and may
        # this user touch it?", which is not specific to recording.
        channel._check_softphone_recording_active()
        number = (payload.get('number') or '').strip()
        if not number:
            raise UserError('No number to forward the call to.')

        client = self.env['connect.settings'].get_voicetel_client()
        other_sid = channel._forward_target_sid(client)

        pbx_user = (
            channel.caller_pbx_user
            or channel.called_pbx_user
            or self.env.user.connect_user
        )
        application = pbx_user.voicetel_domain.application or pbx_user.voicetel_application
        if not application or not application.voice_url:
            raise UserError(
                'No VoiceML application is configured to route the forwarded '
                'call. Set a SIP domain application in VoiceTel settings.')

        # Announce before moving them. Being redirected mid-sentence with no
        # warning reads as a dropped call; a short line and a beat of silence
        # is what the other Connect generation plays here too.
        response = VoiceResponse()
        response.say('Transferring your call now.')
        response.pause(length=1)
        response.redirect(
            self._url_with_query(application.voice_url, {'forward_to': number}),
            method='POST',
        )

        try:
            client.calls.update(other_sid, UpdateCallRequest(Twiml=str(response)))
        except Exception as e:
            logger.exception('Could not forward call %s to %s', other_sid, number)
            raise UserError('Could not forward the call: {}'.format(e))

        debug(self, 'Forwarded channel %s to %s' % (other_sid, number))
        return {'forwarded_to': number, 'channel_sid': other_sid}

    def _forward_target_sid(self, client):
        """The SID of the leg to move: the other party on this call.

        The ledger answers this without a round-trip, and answers it the same
        way in both directions -- the sibling of the softphone's leg is the
        customer on an inbound call and the callee on an outbound one, and is
        never our own leg, so the `<Dial>` we are running cannot be torn down
        underneath us.

        It only answers when the ledger is complete, though. A channel row
        still in flight, or a third leg left up by a ring group, and there is
        no single sibling to pick. VoiceTel knows regardless, so fall back to
        asking it rather than refusing a transfer the user can see is
        possible.
        """
        self.ensure_one()
        siblings = (self.call.channels - self).filtered(
            lambda c: c.status not in CALL_END_STATUSES)
        if len(siblings) == 1:
            return siblings.sid

        logger.info(
            'Ledger shows %s other live legs on call %s; asking VoiceTel which '
            'leg to forward', len(siblings), self.call.id)
        try:
            live = self._voicetel_sibling_sid(client)
        except Exception as e:
            logger.exception('Could not ask VoiceTel for the other leg of %s', self.sid)
            raise UserError('Could not work out which party to forward: {}'.format(e))
        if not live:
            raise UserError(
                'This call cannot be forwarded: there is no other party on '
                'the line.')
        return live

    def _voicetel_sibling_sid(self, client):
        """Ask VoiceTel for the other leg: our parent, or failing that our child.

        A softphone leg is the child on an inbound call (the customer dialled
        in and the platform dialled us) and the parent on an outbound one (we
        dialled out), so the other party is whichever of the two we are not.
        """
        self.ensure_one()
        ours = client.calls.get(self.sid)
        parent_sid = getattr(ours, 'parent_call_sid', None)
        if parent_sid:
            return parent_sid
        for child in client.calls.list(parent_call_sid=self.sid, page_size=20).calls:
            if child.status not in CALL_END_STATUSES:
                return child.sid
        return None

    @api.model
    def _url_with_query(self, url, params):
        """Add query parameters to a URL that may already carry a fragment.

        A voice URL may carry a fragment; appending `?x=y` naively would
        bury the query inside it and the platform would never send it.
        """
        parts = urlsplit(url)
        query = '&'.join(filter(None, [parts.query, urlencode(params)]))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    def voicetel_notify(
        self, title='Connect', sticky=False, warning=False
    ):
        """Notify user about incoming call."""
        # The message is rendered as trusted HTML (markup()) on the
        # client, and self.caller / self.partner.name are attacker-
        # controlled (inbound caller-id, partner name), so every dynamic
        # value is HTML-escaped before interpolation to prevent XSS.
        caller = escape(self.caller or '')
        caller_avatar = '/web/static/img/placeholder.png'
        if self.partner:
            caller = """
                <p class="text-center"><strong>Partner:</strong>
                <a href='/web#id={}&model={}&view_type=form'>
                    {}
                </a>
                </p>
            """.format(self.partner.id, 'res.partner', escape(self.partner.name or ''))
            caller_avatar = '/web/image/res.partner/{}/image_1024'.format(
                self.partner.id
            )
        elif self.caller_user:
            caller_avatar = '/web/image/res.users/{}/image_1024'.format(
                self.caller_user.id
            )

        message = """
        <div class="d-flex align-items-center justify-content-center">
            <div>
                <img style="max-height: 100px; max-width: 100px;"
                        class="rounded-circle"
                        src="{}"/>
            </div>
            <div>
                <p class="text-center">Incoming call</p>
                {}
            </div>
        </div>
        """.format(caller_avatar, caller)

        if release.version_info[0] < 15:
            self.env['bus.bus'].sendone(
                'connect_actions_{}'.format(self.called_user.id),
                {
                    'action': 'notify',
                    'message': message,
                    'title': title,
                    'sticky': sticky,
                    'warning': warning,
                },
            )
        else:
            self.env['bus.bus']._sendone(
                'connect_actions_{}'.format(self.called_user.id),
                'connect_notify',
                {
                    'message': message,
                    'title': title,
                    'sticky': sticky,
                    'warning': warning,
                },
            )
        return True
