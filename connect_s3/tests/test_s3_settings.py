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

    def test_unrelated_write_keeps_the_stored_secret(self):
        settings = self._settings()
        settings.write({"display_aws_secret_access_key": "SECRETVALUE"})
        # A later write that does not mention the secret must not clobber it
        # with the masked display value.
        settings.write({"aws_s3_prefix": "recordings"})
        self.assertEqual(settings.aws_secret_access_key, "SECRETVALUE")
        self.assertEqual(
            settings.display_aws_secret_access_key, "*" * len("SECRETVALUE")
        )

    # ---- provisioning guards (the happy paths need live AWS/Twilio) ----

    def test_provision_requires_bucket(self):
        from odoo.exceptions import ValidationError
        settings = self._settings()
        settings.write({"aws_s3_bucket": False, "aws_region": "eu-central-1"})
        with self.assertRaises(ValidationError):
            settings.action_provision_s3_bucket()

    def test_create_twilio_credential_requires_aws_keys(self):
        from odoo.exceptions import ValidationError
        settings = self._settings()
        settings.write({
            "aws_access_key_id": False,
            "display_aws_secret_access_key": False,
        })
        settings.with_context(skip_protected_fields=True).sudo().write(
            {"aws_secret_access_key": False}
        )
        with self.assertRaises(ValidationError):
            settings.action_create_twilio_aws_credential()

    def test_recreate_twilio_credential_requires_aws_keys(self):
        from odoo.exceptions import ValidationError
        settings = self._settings()
        settings.write({"aws_access_key_id": False})
        settings.with_context(skip_protected_fields=True).sudo().write(
            {"aws_secret_access_key": False}
        )
        with self.assertRaises(ValidationError):
            settings.action_recreate_twilio_aws_credential()
