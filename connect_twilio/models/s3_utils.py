# -*- coding: utf-8 -*-
"""Pure helpers for S3 recording storage.

No Odoo, boto3 or Twilio imports here on purpose: keep this unit-testable in
isolation, and reusable if S3 storage is ever generalized beyond Twilio.
"""
import json
from datetime import timedelta
from urllib.parse import urlparse


# Bucket names are auto-prefixed so they stay inside the IAM policy's allowed
# ARN (arn:aws:s3:::oduist-connect-*). Keep this in sync with build_iam_policy.
S3_BUCKET_PREFIX = "oduist-connect-"


def normalize_bucket_name(name, prefix=S3_BUCKET_PREFIX):
    """Ensure the bucket name starts with `prefix` (idempotent).

    Blank stays blank. A name already starting with the prefix is returned
    unchanged; otherwise the prefix is prepended. The admin only needs to type
    a suffix (e.g. "recordings-acme" -> "oduist-connect-recordings-acme").
    """
    name = (name or "").strip()
    if not name:
        return name
    return name if name.startswith(prefix) else prefix + name


def build_iam_policy(prefix=S3_BUCKET_PREFIX):
    """Return the least-privilege AWS IAM policy (pretty JSON) for the S3 key.

    Bucket ARNs are derived from `prefix`, so the policy always matches the
    auto-prefixed bucket names. Attach it to the IAM user whose access key is
    entered in Connect Settings; it grants only bucket create/configure and
    object read/write under the prefix, no `iam:*`.
    """
    bucket_arn = "arn:aws:s3:::{}*".format(prefix)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CreateAndConfigureBucket",
                "Effect": "Allow",
                "Action": [
                    "s3:CreateBucket",
                    "s3:PutBucketPublicAccessBlock",
                    "s3:PutEncryptionConfiguration",
                    "s3:PutLifecycleConfiguration",
                    "s3:GetBucketLocation",
                ],
                "Resource": bucket_arn,
            },
            {
                "Sid": "ReadWriteObjects",
                "Effect": "Allow",
                "Action": [
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts",
                    "s3:ListBucketMultipartUploads",
                ],
                "Resource": [bucket_arn, bucket_arn + "/*"],
            },
        ],
    }
    return json.dumps(policy, indent=2)


def build_s3_url(bucket, region, prefix):
    """Return the Twilio-ready https URL for a bucket+prefix (no trailing slash)."""
    prefix = (prefix or "").strip("/")
    base = "https://{}.s3.{}.amazonaws.com".format(bucket, region)
    return "{}/{}".format(base, prefix) if prefix else base


def is_s3_media_url(media_url, bucket):
    """True if media_url points at our S3 bucket (any AWS S3 host style).

    The bucket must match a whole host label or a whole leading path segment,
    never a bare substring: buckets that share a prefix ("acme" / "acme2") are
    different buckets, and a bucket name appearing inside an object key does not
    make the URL ours.
    """
    if not media_url or not bucket:
        return False
    parsed = urlparse(media_url)
    host = parsed.hostname or ""
    if not host.endswith("amazonaws.com"):
        return False
    # Virtual-hosted style: <bucket>.s3.<region>.amazonaws.com/<key>
    if host.startswith("{}.".format(bucket)):
        return True
    # Path style: s3.<region>.amazonaws.com/<bucket>/<key>
    path = (parsed.path or "").lstrip("/")
    return path.startswith("{}/".format(bucket))


def parse_s3_key(media_url, bucket):
    """Extract the S3 object key from a full https S3 URL.

    Handles virtual-hosted ("bucket.s3...amazonaws.com/key") and
    path-style ("s3...amazonaws.com/bucket/key").

    NOTE: written against Twilio's documented behavior, not against an
    observed object — the exact key layout Twilio writes has never been
    confirmed live. See specs/decisions/060-s3-recording-storage.md. This is
    the first place to adjust if playback 404s.
    """
    parsed = urlparse(media_url)
    host = parsed.hostname or ""
    path = (parsed.path or "").lstrip("/")
    if host.startswith("{}.".format(bucket)):
        return path
    if path.startswith("{}/".format(bucket)):
        return path[len(bucket) + 1:]
    return path


def build_lifecycle_config(prefix, days):
    """S3 lifecycle config that expires objects under prefix after `days`."""
    prefix = (prefix or "").strip("/")
    return {
        "Rules": [{
            "ID": "connect-recordings-retention",
            "Filter": {"Prefix": "{}/".format(prefix) if prefix else ""},
            "Status": "Enabled",
            "Expiration": {"Days": int(days)},
        }]
    }


def is_recording_expired(start_time, retention_days, now):
    """True if a recording's S3 object has passed its lifecycle expiry."""
    if not retention_days or not start_time:
        return False
    return now >= start_time + timedelta(days=int(retention_days))
