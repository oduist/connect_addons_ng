# -*- coding: utf-8 -*-
import logging

from odoo import fields, models, api, release

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
