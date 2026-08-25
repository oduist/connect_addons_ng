# -*- coding: utf-8 -*-
import json

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestS3Settings(TransactionCase):

    def _settings(self):
        settings = self.env["connect.settings"].sudo().search([], limit=1)
        if not settings:
            settings = self.env["connect.settings"].sudo().with_context(
                no_constrains=True
            ).create({})
        return settings

    def test_bucket_name_gets_default_prefix(self):
        settings = self._settings()
        settings.write({"aws_s3_bucket": "recordings-acme"})
        self.assertEqual(
            settings.aws_s3_bucket_name, "oduist-connect-recordings-acme"
        )

    def test_bucket_name_honours_custom_prefix(self):
        settings = self._settings()
        settings.write({
            "aws_s3_bucket_prefix": "my-prefix-",
            "aws_s3_bucket": "acme",
        })
        self.assertEqual(settings.aws_s3_bucket_name, "my-prefix-acme")

    def test_s3_url_compute_uses_full_bucket_name(self):
        settings = self._settings()
        settings.write({
            "aws_s3_bucket": "my-bucket",
            "aws_region": "eu-central-1",
            "aws_s3_prefix": "recordings",
        })
        # The prefix is applied before the URL is built — the URL must carry
        # the FULL bucket name, not what the admin typed.
        self.assertEqual(
            settings.aws_s3_url,
            "https://oduist-connect-my-bucket.s3.eu-central-1.amazonaws.com/recordings",
        )

    def test_s3_url_empty_without_bucket(self):
        settings = self._settings()
        settings.write({"aws_s3_bucket": False, "aws_region": "us-east-1"})
        self.assertFalse(settings.aws_s3_url)

    def test_iam_policy_tracks_bucket_prefix(self):
        settings = self._settings()
        settings.write({"aws_s3_bucket_prefix": "my-prefix-"})
        doc = json.loads(settings.aws_iam_policy)
        create = next(
            s for s in doc["Statement"] if s["Sid"] == "CreateAndConfigureBucket"
        )
        self.assertEqual(create["Resource"], "arn:aws:s3:::my-prefix-*")

    def test_secret_is_stored_and_masked(self):
        settings = self._settings()
        settings.write({"display_aws_secret_access_key": "SECRETVALUE"})
        self.assertEqual(settings.aws_secret_access_key, "SECRETVALUE")
        self.assertEqual(
            settings.display_aws_secret_access_key, "*" * len("SECRETVALUE")
        )
