# -*- coding: utf-8 -*-
"""Recording upload webhook tests."""
import time

from odoo.tests import tagged, HttpCase

from .common import AGENT_TOKEN

WAV = b'RIFF\x00\x00\x00\x00WAVEfmt fake-audio-payload'


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestRecordingWebhook(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['connect.settings'].set_param(
            'asterisk_agent_token', AGENT_TOKEN)
        cls.Channel = cls.env['connect.channel']
        cls.Recording = cls.env['connect.recording']

    def _put(self, filename, data=WAV, token=AGENT_TOKEN):
        headers = {'Content-Type': 'application/octet-stream'}
        if token:
            headers['Authorization'] = 'Bearer %s' % token
        return self.opener.put(
            self.base_url() + '/asterisk/webhook/recording/%s' % filename,
            data=data, headers=headers, timeout=30)

    def _new_channel(self, sid):
        self.Channel.on_ami_new_channel({
            'Event': 'Newchannel', 'Uniqueid': sid, 'Linkedid': sid,
            'Channel': 'PJSIP/trunk-9000', 'CallerIDNum': '+15550002222',
            'Exten': '101', 'ChannelStateDesc': 'Ring',
            'EventTime': time.time(),
        })
        return self.Channel.search([('sid', '=', sid)])

    def test_requires_token(self):
        self.assertEqual(self._put('uid-x.wav', token=None).status_code, 401)
        self.assertEqual(
            self._put('uid-x.wav', token='wrong').status_code, 401)

    def test_recording_after_channel_links_immediately(self):
        channel = self._new_channel('uid-rec-1')
        response = self._put('uid-rec-1.wav')
        self.assertEqual(response.status_code, 200)
        recording = self.Recording.search([('call_sid', '=', 'uid-rec-1')])
        self.assertTrue(recording)
        self.assertEqual(recording.channel, channel)
        self.assertEqual(recording.call, channel.call)
        self.assertEqual(recording.source, 'asterisk')
        self.assertTrue(recording.recording_attachment)

    def test_recording_before_channel_linked_on_hangup(self):
        response = self._put('uid-rec-2.wav')
        self.assertEqual(response.status_code, 200)
        recording = self.Recording.search([('call_sid', '=', 'uid-rec-2')])
        self.assertTrue(recording)
        self.assertFalse(recording.channel)
        channel = self._new_channel('uid-rec-2')
        self.Channel.on_ami_hangup({
            'Event': 'Hangup', 'Uniqueid': 'uid-rec-2',
            'Linkedid': 'uid-rec-2', 'Channel': 'PJSIP/trunk-9000',
            'CallerIDNum': '+15550002222', 'Exten': '101',
            'ChannelStateDesc': 'Up', 'Cause': '16',
            'EventTime': time.time(),
        })
        self.assertEqual(recording.channel, channel)
        self.assertEqual(recording.call, channel.call)

    def test_duplicate_upload_skipped(self):
        self._new_channel('uid-rec-3')
        self.assertEqual(self._put('uid-rec-3.wav').status_code, 200)
        self.assertEqual(self._put('uid-rec-3.wav').status_code, 200)
        self.assertEqual(self.Recording.search_count(
            [('call_sid', '=', 'uid-rec-3')]), 1)

    def test_empty_body_rejected(self):
        self.assertEqual(self._put('uid-rec-4.wav', data=b'').status_code,
                         400)
