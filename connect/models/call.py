import logging
from markupsafe import escape
from odoo import fields, models, api, release, SUPERUSER_ID
from .settings import debug

logger = logging.getLogger(__name__)

CALL_END_STATUSES = ['completed', 'busy', 'failed', 'no-answer', 'canceled']


class Call(models.Model):
    _name = 'connect.call'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Call'
    _order = 'id desc'

    name = fields.Char(compute='_get_name')
    channels = fields.One2many('connect.channel', 'call', readonly=True)
    recording = fields.Many2one('connect.recording', compute='_get_recording_data')
    transcript = fields.Text(compute='_get_recording_data')
    if release.version_info[0] >= 17.0:
        recording_widget = fields.Html(compute='_get_recording_data', sanitize=False)
    else:
        recording_widget = fields.Char(compute='_get_recording_data')
    recording_icon = fields.Html(compute='_get_recording_data', string='R')
    summary = fields.Html()
    called = fields.Char(readonly=True)
    caller = fields.Char(readonly=True)
    parent_call = fields.Many2one('connect.call', ondelete='cascade', readonly=True)
    partner = fields.Many2one('res.partner', ondelete='set null')
    partner_img = fields.Binary(related='partner.image_1920', string='Partner Image')
    direction = fields.Char(index=True, readonly=True)
    call_type = fields.Selection([
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp')
    ], default='phone', index=True)
    status = fields.Char(readonly=True)
    duration = fields.Integer(string='Seconds', readonly=True)
    duration_minutes = fields.Float(string='Minutes', compute='_get_duration_human', store=True)
    duration_human = fields.Char(compute='_get_duration_human', string='Duration', store=True)
    caller_pbx_user = fields.Many2one('connect.user', ondelete='set null', string='Caller PBX User', readonly=True)
    answered_pbx_user = fields.Many2one('connect.user', ondelete='set null', string='Answered PBX User', readonly=True)
    called_pbx_users = fields.Many2many('connect.user', readonly=True)
    caller_user = fields.Many2one('res.users', string='Caller User', ondelete='set null', readonly=True)
    caller_user_img = fields.Binary(related='caller_user.image_1920')
    called_users = fields.Many2many('res.users', readonly=True)
    answered_user = fields.Many2one('res.users', ondelete='set null', string='Answered User', readonly=True)
    answered_user_img = fields.Binary(related='answered_user.image_1920', string='Answered User Avatar')
    scheduled_datetime = fields.Datetime()
    voicemail_url = fields.Char(readonly=True)
    voicemail_duration = fields.Integer(readonly=True)
    voicemail_icon = fields.Html(compute='_get_voicemail_icon', string='V', store=True)
    if release.version_info[0] >= 17.0:
        voicemail_widget = fields.Html(compute='_get_voicemail_widget', string='VoiceMail', sanitize=False)
    else:
        voicemail_widget = fields.Char(compute='_get_voicemail_widget', string='VoiceMail')
    ref = fields.Reference(selection=[('res.partner', 'Partner')], compute='_get_ref')
    has_error = fields.Boolean(index=True)
    error_code = fields.Char(readonly=True)
    error_message = fields.Text(readonly=True)

    def _get_name(self):
        for rec in self:
            try:
                started = fields.Datetime.context_timestamp(rec, rec.create_date)
                formatted_time = fields.Datetime.to_string(started)
                rec.name = '{} {} call at {}'.format(rec.status, rec.direction, formatted_time).capitalize()
            except Exception:
                logger.exception('Call name compute error:')
                rec.name = str(rec.id)

    def _get_ref(self):
        for rec in self:
            if rec.partner:
                rec.ref = 'res.partner,{}'.format(rec.partner.id)
            else:
                rec.ref = False

    def _get_recording_data(self):
        recordings = self.env['connect.recording'].search([('call', 'in', [k.id for k in self])])
        for rec in self:
            recording = recordings.filtered(lambda x: x.call.id == rec.id)
            if recording:
                recording = max(recording, key=lambda x: x.id)
                rec.recording = recording
                rec.transcript = recording.transcript
                rec.recording_icon = '<span class="fa fa-file-sound-o"/>'
                rec.recording_widget = recording.recording_widget
            else:
                rec.recording_icon = ''
                rec.transcript = ''
                rec.recording = False
                rec.recording_widget = ''

    def _get_voicemail_widget(self):
        proxy_recordings = self.env['connect.settings'].sudo().get_param('proxy_recordings')
        for rec in self:
            if rec.voicemail_url:
                if rec.voicemail_url.startswith('/'):
                    media_url = rec.voicemail_url
                elif proxy_recordings:
                    media_url = '/connect/voicemail/{}'.format(rec.id)
                else:
                    media_url = rec.voicemail_url
                # voicemail_url is webhook-supplied; escape it before it
                # lands in the sanitize=False Html field (stored XSS).
                rec.voicemail_widget = '<audio id="sound_file" preload="auto" ' \
                    'controls="controls"> ' \
                    '<source src="{}"/>' \
                    '</audio>'.format(escape(media_url))
            else:
                rec.voicemail_widget = ''

    @api.depends('voicemail_url')
    def _get_voicemail_icon(self):
        for rec in self:
            if rec.voicemail_url:
                rec.voicemail_icon = '<span class="fa fa-envelope-o"/>'
            else:
                rec.voicemail_icon = ''

    @api.depends('duration')
    def _get_duration_human(self):
        for record in self:
            if record.duration is not None:
                minutes = record.duration // 60
                seconds = record.duration % 60
                record.duration_human = '{:02}:{:02}'.format(minutes, seconds)
                record.duration_minutes = record.duration / 60.0
            else:
                record.duration_minutes = 0
                record.duration_human = "00:00"

    def write(self, vals):
        return super().write(vals)

    @api.model
    def process_call_event(self, channel, error_data=None):
        """Process call event after channel has been created/updated.

        Provider modules call this after process_channel_event() to create
        or update the call record from channel data.

        Args:
            channel: connect.channel record
            error_data: optional dict with 'error_code', 'error_message'

        Returns:
            call id or False
        """
        self = self.sudo()

        if not channel:
            logger.error('No channel passed to process_call_event!')
            return False

        if not self.env['oduist.license'].check_license('connect', silent=True):
            return False


        if not channel.parent_channel and not channel.call:
            # First leg: create a new call
            direction = self._determine_direction(channel)
            call = self.with_context(tracking_disable=True).create({
                'partner': channel.partner.id,
                'called': channel.called_number,
                'caller': channel.caller_number,
                'status': channel.status,
                'caller_pbx_user': channel.caller_pbx_user.id,
                'caller_user': channel.caller_user.id,
                'direction': direction,
                'call_type': channel.call_type or 'phone',
            })
            channel.call = call
        elif channel.parent_channel and channel.parent_channel.call:
            # Secondary leg: assign call from parent
            channel.call = channel.parent_channel.call
            # Detect internal calls
            if ((channel.caller_pbx_user
                    and channel.parent_channel.called_pbx_user)
                    or (channel.called_pbx_user
                        and channel.parent_channel.caller_pbx_user)):
                channel.call.direction = 'internal'

        if not channel.call:
            logger.warning('Channel %s has no associated call.', channel.id)
            return False

        # Update call status from the latest channel
        channel.call.status = channel.call.channels.sorted(
            key='id', reverse=True)[0].status
        # Update call duration from the first channel
        channel.call.duration = channel.call.channels.sorted(
            key='id', reverse=False)[0].duration

        # Set called from 2nd leg for click2call external calls
        if (channel.parent_channel
                and channel.parent_channel.technical_direction == 'outbound-api'):
            channel.call.called = channel.called_number

        # Add called users (avoid duplicates)
        if (channel.called_user
                and channel.called_user not in channel.call.called_users):
            channel.call.called_users = [(4, channel.called_user.id)]
        if (channel.called_pbx_user
                and channel.called_pbx_user not in channel.call.called_pbx_users):
            channel.call.called_pbx_users = [(4, channel.called_pbx_user.id)]

        # Set the answered user on completed calls
        if channel.call.status == 'completed':
            answered_pbx_user = channel.call.channels[0].called_pbx_user
            if answered_pbx_user:
                channel.call.answered_pbx_user = answered_pbx_user
                channel.call.answered_user = answered_pbx_user.user

        # Copy partner from child channel if missing on call
        if not channel.call.partner and channel.partner:
            channel.call.partner = channel.partner

        # Handle errors
        if error_data:
            channel.call.update({
                'has_error': True,
                'error_code': error_data.get('error_code'),
                'error_message': error_data.get('error_message'),
            })

        # Register call when ALL channels have ended
        if channel.status in CALL_END_STATUSES:
            all_ended = all(
                ch.status in CALL_END_STATUSES
                for ch in channel.call.channels
            )
            if all_ended:
                self.register_call(channel, {})

        # Reload call view
        self.env['connect.settings'].connect_reload_view('connect.call')

        return channel.call.id

    def _determine_direction(self, channel):
        """Determine call direction from channel metadata."""
        if channel.technical_direction == 'outbound-api':
            return 'outgoing'
        elif channel.technical_direction == 'inbound' and channel.caller_pbx_user:
            return 'outgoing'
        elif channel.technical_direction == 'inbound' and not channel.caller_pbx_user:
            return 'incoming'
        return 'outgoing'

    def register_call(self, channel, params):
        try:
            notify_users = []
            message = [channel.call.status.capitalize(), channel.call.direction,
                       'call at {}, '.format(channel.create_date.strftime('%Y-%m-%d %H:%M:%S'))]
            if channel.call.caller_user:
                message.append('caller: {}, '.format(channel.call.caller_user.name))
            if channel.call.duration:
                message.append('duration: {}, '.format(channel.call.duration_human))
            if channel.call.answered_user:
                message.append('answered by: {}, '.format(channel.call.answered_user.name))
            if channel.call.called_users:
                message.append('dialed users: {}, '.format(', '.join(k.name for k in channel.call.called_users)))
                for user in channel.call.called_users:
                    # A dialed res.users may have no linked connect.user;
                    # slice to [:1] so an empty recordset reads as False
                    # instead of raising IndexError and aborting the whole
                    # chatter + missed-call notification block.
                    if user.connect_user[:1].missed_calls_notify:
                        notify_users.append(user)
            if channel.call.partner:
                message.insert(3, 'partner: {}, '.format(channel.call.partner.name))
                final_message = ' '.join(message)
                if final_message.endswith(', '):
                    final_message = final_message[:-2] + '.'
                channel.call.register_call_post_message(
                    channel.call.partner, body=final_message, subtype_xmlid='mail.mt_note')
            statuses = ['completed']
            if channel.call.direction == 'incoming' and channel.call.status not in statuses and notify_users:
                debug(self, 'Missed call notification to users: {}'.format(notify_users))
                final_message = ' '.join(message)
                if final_message.endswith(', '):
                    final_message = final_message[:-2] + '.'
                channel.call.register_call_post_message(
                    channel.call,
                    subtype_xmlid='mail.mt_comment',
                    subject=channel.call.name,
                    body=final_message,
                    partner_ids=[k.partner_id.id for k in notify_users]
                )
        except Exception:
            # logger.exception already attaches the traceback; passing the
            # exception as a % arg to a placeholder-free string raised a
            # logging error and hid the real one.
            logger.exception('Register call error')

    def register_call_post_message(self, obj, **kwargs):
        try:
            obj.with_user(SUPERUSER_ID).with_context(mail_create_nosubscribe=False).message_post(**kwargs)
        except Exception:
            logger.exception('Register call error: ')

    def register_summary_to_rec(self, rec, summary):
        try:
            if release.version_info[0] < 14:
                rec.sudo(SUPERUSER_ID).message_post(body=summary)
            else:
                rec.with_user(SUPERUSER_ID).message_post(body=summary)
        except Exception as e:
            logger.error('Cannot register summary: %s', e)

    @api.constrains('summary')
    def register_partner_call_summary(self):
        reload_view = False
        register_summary = self.env['connect.settings'].sudo().get_param('register_summary')
        if not register_summary:
            return
        for rec in self:
            if rec.partner and rec.summary:
                self.register_summary_to_rec(rec.partner, rec.summary)
                reload_view = True
        if reload_view:
            self.env['connect.settings'].connect_reload_view('res.partner')

    def create_partner_button(self):
        self.ensure_one()
        name_number = self.caller if self.direction == 'incoming' else self.called
        context = {
            'connect_call_id': self.id,
            'default_phone': name_number,
        }
        if not self.partner:
            partner = self.env['res.partner'].get_partner_by_number(name_number)
            if partner:
                self.sudo().partner = partner
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner.id,
            'name': self.partner.name if self.partner else 'New Partner',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }

    def transfer_button(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'connect.transfer_wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Transfer Wizard'
        }

    def redial(self):
        self.ensure_one()
        self.env['connect.settings'].originate_call(
            number=self.called if self.direction == 'outgoing' else self.caller,
        )

    @api.model
    def get_widget_calls(self, domain, limit=None, offset=0, order='id desc', fields=[]):
        calls = self.search(domain, offset, limit, order)
        payload = []
        read_fields = self.get_widget_fields()
        if isinstance(fields, list):
            read_fields.extend(fields)
        for call in calls:
            call_data = call.read(read_fields)[0]
            if call.called_users:
                call_data.update({'called_users': list(call.called_users.read(['id', 'name'])[0].values())})
            payload.append(call_data)
        return payload

    def get_widget_fields(self):
        return [
            "id",
            "called",
            "caller",
            "caller_user",
            "called_users",
            "partner",
            "create_date",
            "direction"
        ]
