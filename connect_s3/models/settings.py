# -*- coding: utf-8 -*-
import logging

import requests
from odoo import fields, models, api, release
from odoo.exceptions import ValidationError

from odoo.addons.connect.models.license import ODUIST_MODULES

from . import s3_utils

ODUIST_MODULES.append('connect_s3')

logger = logging.getLogger(__name__)

S3_PROTECTED_FIELDS = [
    "display_aws_secret_access_key",
]


class Settings(models.Model):
    _inherit = 'connect.settings'

    s3_recordings_enabled = fields.Boolean(
        string="Store recordings in S3",
        help="Turn on to configure and use AWS S3 storage (reveals the settings "
             "below). Recordings are read from S3 only once a bucket is configured "
             "and Twilio uploads there; otherwise they keep playing from Twilio.",
    )
    aws_access_key_id = fields.Char(string="AWS Access Key ID")
    aws_secret_access_key = fields.Char(
        string="AWS Secret Access Key", groups="base.group_erp_manager"
    )
    display_aws_secret_access_key = fields.Char()
    aws_region = fields.Selection(
        selection=[
            ("eu-central-1", "EU (Frankfurt)"),
            ("eu-west-1", "EU (Ireland)"),
            ("us-east-1", "US East (N. Virginia)"),
            ("us-west-2", "US West (Oregon)"),
            ("ap-southeast-1", "Asia Pacific (Singapore)"),
        ],
        string="AWS Region", default="eu-central-1", required=True,
    )
    aws_s3_bucket_prefix = fields.Char(
        string="S3 Bucket Prefix", default=lambda self: s3_utils.S3_BUCKET_PREFIX,
        help="Bucket names are forced to start with this prefix, and the IAM policy "
             "above is scoped to it. Default 'oduist-connect-'. Set your own to match "
             "an existing IAM naming convention (leave empty to use the default).",
    )
    aws_s3_bucket = fields.Char(
        string="S3 Bucket Name",
        help="The bucket name (or just a suffix). The prefix above is combined with "
             "it dynamically to form the full bucket name shown below.",
    )
    aws_s3_bucket_name = fields.Char(
        string="Full Bucket Name", compute="_compute_aws_s3_bucket_name", readonly=True,
        help="Actual bucket = prefix + name. Used for provisioning, the S3 URL and "
             "playback.",
    )
    aws_s3_prefix = fields.Char(string="S3 Folder (prefix)", default="recordings")
    s3_retention_days = fields.Integer(
        string="Retention (days)", default=0,
        help="0 = keep forever. >0 sets an S3 lifecycle rule that deletes the audio "
             "file after N days (the recording row and transcript are kept).",
    )
    aws_s3_url = fields.Char(
        string="S3 URL (paste into Twilio)", compute="_compute_aws_s3_url", readonly=True,
    )
    aws_iam_policy = fields.Text(
        string="AWS IAM Policy", compute="_compute_aws_iam_policy", readonly=True,
        help="Least-privilege policy to attach to the AWS IAM user whose access "
             "key you enter below. Copy it into IAM -> Users -> Add inline policy.",
    )
    twilio_aws_credential_sid = fields.Char(
        string="Twilio AWS Credential SID", readonly=True,
    )

    def _effective_s3_prefix(self):
        """The bucket prefix actually in force (blank field falls back)."""
        self.ensure_one()
        return self.aws_s3_bucket_prefix or s3_utils.S3_BUCKET_PREFIX

    @api.depends("aws_s3_bucket", "aws_s3_bucket_prefix")
    def _compute_aws_s3_bucket_name(self):
        for rec in self:
            rec.aws_s3_bucket_name = s3_utils.normalize_bucket_name(
                rec.aws_s3_bucket, rec._effective_s3_prefix()
            )

    @api.depends("aws_s3_bucket_name", "aws_region", "aws_s3_prefix")
    def _compute_aws_s3_url(self):
        for rec in self:
            if rec.aws_s3_bucket_name and rec.aws_region:
                rec.aws_s3_url = s3_utils.build_s3_url(
                    rec.aws_s3_bucket_name, rec.aws_region, rec.aws_s3_prefix
                )
            else:
                rec.aws_s3_url = False

    @api.depends("aws_s3_bucket_prefix")
    def _compute_aws_iam_policy(self):
        for rec in self:
            rec.aws_iam_policy = s3_utils.build_iam_policy(rec._effective_s3_prefix())

    def open_s3_form(self):
        rec = self.search([])
        if not rec:
            rec = self.sudo().with_context(no_constrains=True).create({})
        else:
            rec = rec[0]
        return {
            "type": "ir.actions.act_window",
            "res_model": "connect.settings",
            "res_id": rec.id,
            "name": "S3 Storage",
            "view_mode": "form",
            "view_id": self.env.ref("connect_s3.connect_s3_settings_form").id,
            "target": "current",
        }

    # Friendly name of the credential this module manages on the Twilio side.
    # Used to look one up before creating a duplicate.
    _TWILIO_CREDENTIAL_NAME = "connect-s3-recordings"
    _TWILIO_CREDENTIALS_URL = "https://accounts.twilio.com/v1/Credentials/AWS"

    def _get_s3_client(self):
        """boto3 S3 client built from the singleton settings.

        Imported lazily so the module still loads when boto3 is missing; the
        manifest declares it, but a stale environment should fail at the button
        rather than at registry load.
        """
        import boto3
        rec = self.env["connect.settings"].sudo().search([], limit=1)
        return boto3.client(
            "s3",
            aws_access_key_id=rec.aws_access_key_id,
            aws_secret_access_key=rec.aws_secret_access_key,
            region_name=rec.aws_region,
        )

    def action_provision_s3_bucket(self):
        """Create and configure the bucket: private, SSE-S3, optional lifecycle.

        Idempotent — re-running it on an existing bucket re-applies the
        configuration instead of failing.
        """
        from botocore.exceptions import ClientError
        self.ensure_one()
        if not (self.aws_s3_bucket and self.aws_region):
            raise ValidationError("Set S3 bucket name and region first.")
        s3 = self._get_s3_client()
        prefix = self._effective_s3_prefix()
        bucket = self.aws_s3_bucket_name
        try:
            if self.aws_region == "us-east-1":
                # us-east-1 rejects an explicit LocationConstraint.
                s3.create_bucket(Bucket=bucket)
            else:
                s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": self.aws_region},
                )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "AccessDenied":
                # By far the most common failure: the IAM policy's Resource ARN
                # does not match the auto-added prefix. Say so explicitly.
                raise ValidationError(
                    "AWS denied s3:CreateBucket for '%s'. The '%s' prefix is added "
                    "automatically, so this usually means the IAM policy is not "
                    "attached to this key, or its Resource ARN uses a different "
                    "prefix. Allow s3:CreateBucket on 'arn:aws:s3:::%s*'.\n\n%s"
                    % (bucket, prefix, prefix, e)
                )
            if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise ValidationError("S3 create_bucket failed: %s" % e)
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True, "IgnorePublicAcls": True,
                "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
            },
        )
        s3.put_bucket_encryption(
            Bucket=bucket,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                ]
            },
        )
        if self.s3_retention_days and self.s3_retention_days > 0:
            s3.put_bucket_lifecycle_configuration(
                Bucket=bucket,
                LifecycleConfiguration=s3_utils.build_lifecycle_config(
                    self.aws_s3_prefix, self.s3_retention_days
                ),
            )
        self.connect_notify(
            "S3 bucket '%s' provisioned." % bucket, notify_uid=self.env.uid
        )
        return True

    def _twilio_auth(self):
        """(account_sid, auth_token) for the Twilio accounts API.

        Both fields are added to connect.settings by connect_twilio, which is a
        hard dependency of this module.
        """
        settings = self.env["connect.settings"].sudo()
        return settings.get_param("account_sid"), settings.get_param("auth_token")

    def _aws_credentials_or_raise(self):
        """Return (access_key, secret) or raise if either is missing."""
        self.ensure_one()
        settings = self.env["connect.settings"].sudo()
        access_key = self.aws_access_key_id
        secret = settings.get_param("aws_secret_access_key")
        if not (access_key and secret):
            raise ValidationError("Set AWS access key and secret first.")
        return access_key, secret

    def _create_twilio_credential(self, access_key, secret):
        """POST a new AWS credential to Twilio, store and return its SID."""
        sid, token = self._twilio_auth()
        try:
            resp = requests.post(
                self._TWILIO_CREDENTIALS_URL, auth=(sid, token), timeout=30,
                data={
                    "Credentials": "%s:%s" % (access_key, secret),
                    "FriendlyName": self._TWILIO_CREDENTIAL_NAME,
                },
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ValidationError("Twilio AWS credential request failed: %s" % e)
        self.twilio_aws_credential_sid = resp.json()["sid"]
        return self.twilio_aws_credential_sid

    def _list_twilio_credentials(self):
        """Return the account's AWS credentials, or raise on a transport error."""
        sid, token = self._twilio_auth()
        try:
            existing = requests.get(
                self._TWILIO_CREDENTIALS_URL, auth=(sid, token), timeout=30
            )
            existing.raise_for_status()
        except requests.RequestException as e:
            raise ValidationError("Twilio AWS credential request failed: %s" % e)
        return existing.json().get("credentials", [])

    def _delete_twilio_credential(self, cred_sid):
        """Delete one AWS credential on the Twilio side."""
        sid, token = self._twilio_auth()
        try:
            deleted = requests.delete(
                "%s/%s" % (self._TWILIO_CREDENTIALS_URL, cred_sid),
                auth=(sid, token), timeout=30,
            )
            deleted.raise_for_status()
        except requests.RequestException as e:
            raise ValidationError("Twilio AWS credential request failed: %s" % e)

    def action_create_twilio_aws_credential(self):
        """Create the Twilio-side AWS credential, or adopt an existing one.

        Keeps the AWS keys out of the Twilio Console: the admin only selects
        the resulting credential there.
        """
        self.ensure_one()
        access_key, secret = self._aws_credentials_or_raise()
        for cred in self._list_twilio_credentials():
            if cred.get("friendly_name") == self._TWILIO_CREDENTIAL_NAME:
                self.twilio_aws_credential_sid = cred["sid"]
                self.connect_notify(
                    "Twilio AWS credential '%s' already exists: %s"
                    % (self._TWILIO_CREDENTIAL_NAME, cred["sid"]),
                    notify_uid=self.env.uid,
                )
                return True
        new_sid = self._create_twilio_credential(access_key, secret)
        self.connect_notify(
            "Twilio AWS credential created: %s" % new_sid, notify_uid=self.env.uid
        )
        return True

    def action_recreate_twilio_aws_credential(self):
        """Delete the managed credential and create a fresh one.

        Twilio cannot update a credential's key in place, so rotating the AWS
        keys means replacing the credential. The new SID must be re-selected in
        the Console, hence the sticky notification.
        """
        self.ensure_one()
        access_key, secret = self._aws_credentials_or_raise()
        deleted_sids = []
        for cred in self._list_twilio_credentials():
            if cred.get("friendly_name") == self._TWILIO_CREDENTIAL_NAME:
                self._delete_twilio_credential(cred["sid"])
                deleted_sids.append(cred["sid"])
        try:
            new_sid = self._create_twilio_credential(access_key, secret)
        except Exception as e:
            if not deleted_sids:
                raise
            # Twilio has already committed the deletion; rolling back this
            # transaction cannot undo it, so the stored SID is now stale and
            # Twilio can no longer write recordings to S3. Say so plainly
            # instead of leaving a dead SID on screen looking current.
            raise ValidationError(
                "The old Twilio AWS credential (%s) was DELETED, but creating the "
                "replacement failed: %s\n\nThe SID shown in settings is now stale "
                "and Twilio can no longer upload recordings to S3. Press RECREATE "
                "TWILIO CREDENTIAL again to finish creating a new one, then "
                "re-select it in Twilio Console -> Voice -> Recordings -> Settings."
                % (", ".join(deleted_sids), e)
            )
        self.connect_notify(
            "Twilio AWS credential recreated: %s. Re-select it in Twilio Console "
            "-> Voice -> Recordings -> Settings." % new_sid,
            notify_uid=self.env.uid, sticky=True,
        )
        return True

    def write(self, vals):
        # Mirror-and-mask the AWS secret, same pattern as core PROTECTED_FIELDS
        # and connect_twilio's TWILIO_PROTECTED_FIELDS: the UI binds to the
        # display_ field, the real value is copied across and the display copy
        # is overwritten with asterisks.
        if self.env.context.get("skip_protected_fields"):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        changed_fields = {}
        for field_name in S3_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace("display_", ""): vals.get(field_name),
                        field_name: "*" * len(vals.get(field_name)),
                    }
                )
        if changed_fields:
            self.with_context(skip_protected_fields=True).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
        return res
