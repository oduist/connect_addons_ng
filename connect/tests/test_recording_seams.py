# -*- coding: utf-8 -*-
"""Seams that storage add-ons (connect_twilio S3 storage) override.

These lock the default behavior in place so an add-on that calls super()
keeps getting the documented fallbacks.
"""
import base64
from tempfile import NamedTemporaryFile

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestRecordingSeams(TransactionCase):

    def _recording(self, **vals):
        return self.env["connect.recording"].create(vals)

    def test_get_media_src_returns_proxy_url_when_proxying(self):
        rec = self._recording(media_url="https://example.com/RE1.mp3")
        self.assertEqual(
            rec._get_media_src(True), "/connect/recording/{}".format(rec.id)
        )

    def test_get_media_src_returns_raw_url_when_not_proxying(self):
        rec = self._recording(media_url="https://example.com/RE1.mp3")
        self.assertEqual(rec._get_media_src(False), "https://example.com/RE1.mp3")

    def test_get_media_src_prefers_attachment(self):
        rec = self._recording(
            media_url="https://example.com/RE1.mp3",
            recording_attachment=base64.b64encode(b"audio"),
            recording_filename="RE1.wav",
        )
        self.assertEqual(rec._get_media_src(False), rec.get_attachment_media_url())

    def test_get_media_src_empty_without_media(self):
        rec = self._recording()
        self.assertEqual(rec._get_media_src(False), "")

    def test_fetch_media_to_writes_attachment_bytes(self):
        rec = self._recording(
            recording_attachment=base64.b64encode(b"audio-bytes"),
            recording_filename="RE1.wav",
        )
        with NamedTemporaryFile() as temp_file:
            rec._fetch_media_to(temp_file)
            temp_file.flush()
            temp_file.seek(0)
            self.assertEqual(temp_file.read(), b"audio-bytes")

    def test_recording_widget_uses_media_src(self):
        rec = self._recording(media_url="https://example.com/RE1.mp3")
        self.assertIn("<audio", rec.recording_widget)
        self.assertIn(rec._get_media_src(
            self.env["connect.settings"].sudo().get_param("proxy_recordings")
        ), rec.recording_widget)

    def test_media_download_url_defaults_to_media_url(self):
        rec = self._recording(media_url="https://example.com/RE1.mp3")
        self.assertEqual(
            rec._get_media_download_url(), "https://example.com/RE1.mp3")

    def test_voicemail_src_and_download_defaults(self):
        call = self.env["connect.call"].create({
            "caller": "+15550001111",
            "called": "+15550002222",
            "voicemail_url": "https://example.com/VM1.mp3",
        })
        self.assertEqual(
            call._get_voicemail_src(False), "https://example.com/VM1.mp3")
        self.assertEqual(
            call._get_voicemail_src(True),
            "/connect/voicemail/{}".format(call.id))
        self.assertEqual(
            call._get_voicemail_download_url(), "https://example.com/VM1.mp3")
        call.voicemail_url = "/web/content/1"
        self.assertEqual(call._get_voicemail_src(True), "/web/content/1")
