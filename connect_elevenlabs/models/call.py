import logging

from odoo import models, fields, release, api

logger = logging.getLogger(__name__)


class Call(models.Model):
    _inherit = 'connect.call'

    elevenlabs_agent = fields.Many2one('connect.elevenlabs_agent', string='Agent', readonly=True)
    elevenlabs_summary = fields.Html(readonly=True)
    elevenlabs_transcript = fields.Text(compute='_get_elevenlabs_recording_data')
    elevenlabs_conversation_id = fields.Char(readonly=True)
    if release.version_info[0] >= 17.0:
        elevenlabs_recording_widget = fields.Html(compute='_get_elevenlabs_recording_data', sanitize=False, string='Agent Recording')
    else:
        elevenlabs_recording_widget = fields.Char(compute='_get_elevenlabs_recording_data', string='Agent Recording')


    def _get_recording_data(self):
        super(Call, self)._get_recording_data()
        for rec in self:
            # Also show recording icons on Agent calls when recording exists.
            if rec.elevenlabs_agent and rec.recording:
                rec.recording_icon = '<span class="fa fa-file-sound-o"/>'

    @api.model
    def create_from_elevenlabs_inbound(self, data):
        conversation_id = data.get('conversation_id', '')
        if conversation_id:
            existing = self.sudo().search(
                [('elevenlabs_conversation_id', '=', conversation_id)], limit=1)
            if existing:
                logger.info('EL inbound: call already exists for conversation_id=%s, skipping', conversation_id)
                return existing

        meta = data.get('metadata', {})
        phone_call = meta.get('phone_call', {})
        caller = phone_call.get('external_number', '')
        called = phone_call.get('agent_number', '')
        call_sid = phone_call.get('call_sid', '')
        duration = meta.get('call_duration_secs', 0)

        analysis = data.get('analysis', {})
        status = 'completed' if analysis.get('call_successful') == 'success' else 'failed'

        partner = self.env['res.partner'].sudo().get_partner_by_number(caller) if caller else False
        agent_id = data.get('agent_id', '')
        agent = self.env['connect.elevenlabs_agent'].sudo().search(
            [('agent_uid', '=', agent_id)], limit=1) if agent_id else False

        summary = analysis.get('transcript_summary', '')
        call = self._elevenlabs_existing_call(data, call_sid)
        if call:
            # The call reached the agent through a provider leg, so the ledger
            # already holds it -- complete that record instead of logging the
            # same conversation twice. Caller/called/status/duration stay as
            # the provider reported them: on the SIP-trunk path EL reports the
            # DID as external_number and its own agent id as agent_number.
            vals = {
                'elevenlabs_conversation_id': conversation_id,
                'elevenlabs_summary': summary,
            }
            if agent and not call.elevenlabs_agent:
                vals['elevenlabs_agent'] = agent.id
            if partner and not call.partner:
                vals['partner'] = partner.id
            call.sudo().write(vals)
            partner = call.partner or partner
            caller = call.caller or caller
            called = call.called or called
            logger.info('EL inbound: attached conversation_id=%s to existing connect.call id=%s',
                        conversation_id, call.id)
        else:
            if called and not self.env['connect.twilio.number'].sudo().search(
                    [('phone_number', '=', called)], limit=1):
                logger.warning('EL inbound: connect.number not found for called=%s', called)
            call = self.sudo().create({
                'caller': caller,
                'called': called,
                'direction': 'incoming',
                'status': status,
                'duration': duration,
                'call_sid': call_sid,
                'elevenlabs_conversation_id': conversation_id,
                'elevenlabs_summary': summary,
                'partner': partner.id if partner else False,
                'elevenlabs_agent': agent.id if agent else False,
            })
            logger.info('EL inbound: created connect.call id=%s for conversation_id=%s caller=%s',
                        call.id, conversation_id, caller)
        # Persist the conversation transcript as a connect.recording so it shows
        # on the call form and downstream hooks (e.g. Oduist Memory retain, which
        # observes connect.recording creation) fire. EL already supplies the
        # transcript, so skip the OpenAI/EL re-transcription pass.
        transcript = self._elevenlabs_transcript_text(data.get('transcript'))
        if transcript or summary:
            self.env['connect.recording'].sudo().with_context(
                skip_transcription=True).create({
                    'call': call.id,
                    'partner': partner.id if partner else False,
                    'sid': conversation_id or call_sid,
                    'call_sid': call_sid or conversation_id,
                    'caller_number': caller,
                    'called_number': called,
                    'status': 'completed',
                    'duration': duration,
                    'start_time': call.create_date,
                    'elevenlabs_transcript': transcript,
                    'elevenlabs_summary': summary,
                })
        return call

    @api.model
    def _elevenlabs_existing_call(self, data, call_sid=''):
        """The connect.call this conversation already belongs to, if any.

        `connect.elevenlabs_agent.render()` hands the ledger call id to EL as
        the ``X-Connect-Call-Ref`` SIP header, and EL echoes it back among the
        post-call dynamic variables. A call that reached the agent through a
        provider leg is therefore already logged; only a native EL SIP attach
        arrives with no record.
        """
        init = data.get('conversation_initiation_client_data') or {}
        dynamic = init.get('dynamic_variables') or {}
        for key in ('sip_connect_call_ref', 'call_id'):
            try:
                call = self.sudo().browse(int(dynamic.get(key))).exists()
            except (TypeError, ValueError):
                continue
            if call:
                return call
        if call_sid:
            channel = self.env['connect.channel'].sudo().search(
                [('sid', '=', call_sid)], limit=1)
            if channel.call:
                return channel.call
        return self.browse()

    @staticmethod
    def _elevenlabs_transcript_text(turns):
        """Flatten an EL post-call `transcript` list into `role: message` lines."""
        if not turns:
            return ''
        lines = []
        for turn in turns:
            if not isinstance(turn, dict):
                continue
            message = (turn.get('message') or '').strip()
            if not message:
                continue
            lines.append('{}: {}'.format(turn.get('role') or 'agent', message))
        return '\n'.join(lines)

    def _get_elevenlabs_recording_data(self):
        # Make one query to get all records.
        recordings = self.env['connect.recording'].search([('call', 'in', [k.id for k in self])])
        for rec in self:
            recording = recordings.filtered(lambda x: x.call.id == rec.id and x.elevenlabs_transcript)
            if recording:
                rec.elevenlabs_transcript = recording[0].elevenlabs_transcript
                rec.elevenlabs_recording_widget = recording[0].elevenlabs_recording_widget
            else:
                rec.elevenlabs_transcript = ''
                rec.elevenlabs_recording_widget = ''
