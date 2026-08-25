# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class _FakeS3Client:
    """Stand-in for the boto3 client, so the read path is testable offline."""

    def __init__(self):
        self.presigned_calls = []
        self.downloaded = []

    def generate_presigned_url(self, operation, Params=None, ExpiresIn=None):
        self.presigned_calls.append((operation, Params, ExpiresIn))
        return "https://signed.example.com/{}".format(Params["Key"])

    def download_fileobj(self, bucket, key, fileobj):
        self.downloaded.append((bucket, key))
        fileobj.write(b"s3-audio")


@tagged("post_install", "-at_install")
class TestS3Recording(TransactionCase):

    S3_URL = (
        "https://oduist-connect-testbucket.s3.eu-central-1.amazonaws.com"
        "/recordings/AC1/RE1.mp3"
    )

    def setUp(self):
        super().setUp()
        self.settings = self.env["connect.settings"].sudo().search([], limit=1)
        if not self.settings:
            self.settings = self.env["connect.settings"].sudo().with_context(
                no_constrains=True
            ).create({})
        self.settings.write({
            "s3_recordings_enabled": True,
            "aws_s3_bucket_prefix": "oduist-connect-",
            "aws_s3_bucket": "testbucket",
            "aws_region": "eu-central-1",
            "aws_s3_prefix": "recordings",
            "s3_retention_days": 0,
            "proxy_recordings": False,
        })
        self.fake_s3 = _FakeS3Client()
        self.patch(
            type(self.env["connect.settings"]),
            "_get_s3_client",
            lambda records: self.fake_s3,
        )

    def test_expired_when_past_retention(self):
        self.settings.write({"s3_retention_days": 30})
        rec = self.env["connect.recording"].create({
            "media_url": self.S3_URL,
            "start_time": datetime.now() - timedelta(days=40),
        })
        self.assertTrue(rec.recording_expired)

    def test_not_expired_within_retention(self):
        self.settings.write({"s3_retention_days": 30})
        rec = self.env["connect.recording"].create({
            "media_url": self.S3_URL,
            "start_time": datetime.now() - timedelta(days=1),
        })
        self.assertFalse(rec.recording_expired)

    def test_expired_widget_says_so(self):
        self.settings.write({"s3_retention_days": 30})
        rec = self.env["connect.recording"].create({
            "media_url": self.S3_URL,
            "start_time": datetime.now() - timedelta(days=40),
        })
        self.assertEqual(rec.recording_widget, "<i>Recording expired</i>")

    def test_media_src_is_presigned_for_s3(self):
        rec = self.env["connect.recording"].create({"media_url": self.S3_URL})
        src = rec._get_media_src(False)
        self.assertEqual(src, "https://signed.example.com/recordings/AC1/RE1.mp3")
        operation, params, expires = self.fake_s3.presigned_calls[0]
        self.assertEqual(operation, "get_object")
        self.assertEqual(params["Bucket"], "oduist-connect-testbucket")
        self.assertEqual(params["Key"], "recordings/AC1/RE1.mp3")
        self.assertEqual(expires, 3600)

    def test_media_src_falls_through_for_twilio_url(self):
        twilio_url = "https://api.twilio.com/2010-04-01/Accounts/AC1/Recordings/RE1"
        rec = self.env["connect.recording"].create({"media_url": twilio_url})
        self.assertEqual(rec._get_media_src(False), twilio_url)
        self.assertFalse(self.fake_s3.presigned_calls)

    def test_media_src_respects_proxy_setting(self):
        rec = self.env["connect.recording"].create({"media_url": self.S3_URL})
        self.assertEqual(
            rec._get_media_src(True), "/connect/recording/{}".format(rec.id)
        )
        self.assertFalse(self.fake_s3.presigned_calls)

    def test_media_src_falls_through_when_disabled(self):
        self.settings.write({"s3_recordings_enabled": False})
        rec = self.env["connect.recording"].create({"media_url": self.S3_URL})
        self.assertEqual(rec._get_media_src(False), self.S3_URL)
        self.assertFalse(self.fake_s3.presigned_calls)

    def test_fetch_media_downloads_from_s3(self):
        from tempfile import NamedTemporaryFile
        rec = self.env["connect.recording"].create({"media_url": self.S3_URL})
        with NamedTemporaryFile() as temp_file:
            rec._fetch_media_to(temp_file)
            temp_file.flush()
            temp_file.seek(0)
            self.assertEqual(temp_file.read(), b"s3-audio")
        self.assertEqual(
            self.fake_s3.downloaded,
            [("oduist-connect-testbucket", "recordings/AC1/RE1.mp3")],
        )

    def test_twilio_recording_never_expires_from_s3_retention(self):
        self.settings.write({"s3_retention_days": 30})
        twilio_url = "https://api.twilio.com/2010-04-01/Accounts/AC1/Recordings/RE1"
        rec = self.env["connect.recording"].create({
            "media_url": twilio_url,
            "start_time": datetime.now() - timedelta(days=40),
        })
        # Old, but hosted at Twilio: no S3 lifecycle rule ever applied to it.
        self.assertFalse(rec.recording_expired)
        self.assertIn("<audio", rec.recording_widget)

    def test_s3_recording_not_expired_when_s3_disabled(self):
        self.settings.write({"s3_retention_days": 30, "s3_recordings_enabled": False})
        rec = self.env["connect.recording"].create({
            "media_url": self.S3_URL,
            "start_time": datetime.now() - timedelta(days=40),
        })
        self.assertFalse(rec.recording_expired)

    def test_attachment_recording_never_goes_to_s3(self):
        import base64
        from tempfile import NamedTemporaryFile
        self.settings.write({"s3_retention_days": 30})
        rec = self.env["connect.recording"].create({
            "media_url": self.S3_URL,
            "recording_attachment": base64.b64encode(b"local-audio"),
            "recording_filename": "RE1.wav",
            "start_time": datetime.now() - timedelta(days=40),
        })
        # The attachment wins over an S3-shaped media_url, on every path.
        self.assertEqual(rec._get_media_src(False), rec.get_attachment_media_url())
        with NamedTemporaryFile() as temp_file:
            rec._fetch_media_to(temp_file)
            temp_file.flush()
            temp_file.seek(0)
            self.assertEqual(temp_file.read(), b"local-audio")
        self.assertFalse(rec.recording_expired)
        self.assertFalse(self.fake_s3.presigned_calls)
        self.assertFalse(self.fake_s3.downloaded)
