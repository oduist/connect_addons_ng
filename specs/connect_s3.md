# Connect S3 Module Specification

## Module Info

- **Name:** Oduist Connect S3 Recording Storage
- **Technical:** `connect_s3`
- **Version:** 19.0.1.0.0
- **Depends:** `connect`, `connect_twilio`
- **External dependencies:** `boto3` (python)
- **Application:** False
- **License:** Other proprietary
- **post_init_hook:** stamps the module install date and refreshes the Oduist
  license status (mirrors the per-module hook pattern of the connect suite)
- **ADR:** [060-s3-recording-storage](decisions/060-s3-recording-storage.md)

## Overview

`connect_s3` stores Twilio call recordings in a customer-owned AWS S3 bucket
instead of Twilio's cloud, so the customer owns the media lifecycle and avoids
Twilio storage charges.

The module is a **Twilio add-on**, not a provider-agnostic bridge. It is built
on Twilio's *External S3 Storage* feature: once that feature is enabled on the
Twilio account, **Twilio itself writes the audio into the bucket** and the
`RecordingUrl` Twilio sends to Odoo points at S3 rather than at
`api.twilio.com`. Odoo never uploads anything; it only configures the bucket,
creates the Twilio-side AWS credential, and reads the media back.

Because that write path belongs to Twilio, the module cannot serve
`connect_freeswitch`, `connect_asterisk`, `connect_telnyx`, `connect_infobip`
or `connect_livekit` — hence the hard `connect_twilio` dependency. A
provider-agnostic offload (Odoo pulling recordings and pushing them to S3) was
considered and rejected for v1; see ADR-060.

Responsibilities:

- AWS/S3 configuration and credentials on `connect.settings`
- One-click provisioning of the bucket via boto3 (block-public, SSE-S3,
  lifecycle) and of the Twilio AWS credential via the Twilio accounts API
- Reading recordings back from S3 for playback, proxy download and OpenAI
  transcription, in **mixed mode** — recordings created before the switch stay
  on Twilio and keep working
- Retention through an S3 lifecycle rule, with an "expired" indicator on
  recordings whose audio the lifecycle has already deleted

### What the module deliberately does NOT do

| Not done | Why |
|----------|-----|
| Flip the Twilio *External S3 Storage* toggle | Twilio exposes `RecordingSettings` in its public API for **video only**. For voice the toggle is Console-only (Voice → Recordings → Settings). The admin does it once by hand; the module shows the exact checklist and the two values to paste. |
| Migrate existing Twilio-hosted recordings into S3 | Mixed mode already keeps them playable. A bulk migration is a separate, resumable job. |
| SSE-KMS | SSE-S3 (AES256) is enough for audio at rest and needs no key administration. |
| S3-compatible stores (MinIO, Wasabi, R2) | Twilio's external storage targets AWS S3 specifically; a custom `endpoint_url` would configure a bucket Twilio cannot write to. |

---

## Architecture

```
Twilio  ──writes audio──▶  s3://<bucket>/<prefix>/...
   │                              ▲
   │ RecordingUrl (S3 https URL)  │ boto3 get_object / presigned URL
   ▼                              │
connect.recording.media_url ──▶ connect_s3 read path ──▶ player / transcription
```

`connect_s3` owns **no models of its own**. It extends two existing models
(`connect.settings`, `connect.recording`) and one controller
(`ConnectController`). Consequently it ships **no `ir.model.access.csv`** — there
is no new model to grant access on. Everything it exposes in the UI is gated on
`connect.group_admin`.

---

## Models (connect_s3/models/)

### 1. `s3_utils.py` — pure helpers (no Odoo, no boto3 imports)

Kept free of Odoo and boto3 on purpose so the logic is unit-testable in
isolation, without a database or AWS.

| Function | Description |
|----------|-------------|
| `normalize_bucket_name(name, prefix)` | Idempotently force the bucket name to start with `prefix`. Blank stays blank. Lets the admin type only a suffix (`recordings-acme` → `oduist-connect-recordings-acme`). |
| `build_iam_policy(prefix)` | Least-privilege IAM policy as pretty JSON, with bucket ARNs derived from `prefix` so the policy always matches the auto-prefixed names. Grants bucket create/configure + object read/write under the prefix; no `iam:*`. |
| `build_s3_url(bucket, region, prefix)` | The Twilio-ready `https://{bucket}.s3.{region}.amazonaws.com/{prefix}` URL, no trailing slash. |
| `is_s3_media_url(media_url, bucket)` | True when `media_url` points at our bucket (host ends in `amazonaws.com` and the bucket name occurs in the URL). Distinguishes S3 recordings from Twilio-hosted ones. |
| `parse_s3_key(media_url, bucket)` | Extract the object key, handling both virtual-hosted (`bucket.s3….amazonaws.com/key`) and path-style (`s3….amazonaws.com/bucket/key`) URLs. |
| `build_lifecycle_config(prefix, days)` | S3 lifecycle configuration expiring objects under `prefix` after `days`. Rule ID `connect-recordings-retention`. |
| `is_recording_expired(start_time, retention_days, now)` | True once `start_time + retention_days` has passed. Pure date arithmetic — no S3 call. |

Module constant: `S3_BUCKET_PREFIX = "oduist-connect-"`. It must stay in sync
with the ARNs in `build_iam_policy`.

### 2. `settings.py` — `_inherit = 'connect.settings'`

Registers `'connect_s3'` in `ODUIST_MODULES` (`connect/models/license.py`) for
license tracking, following the pattern of every other module.

**Fields**

| Field | Type | Notes |
|-------|------|-------|
| `s3_recordings_enabled` | Boolean | Master flag. Drives the read path and reveals the rest of the form. |
| `aws_access_key_id` | Char | IAM user's access key ID. |
| `aws_secret_access_key` | Char | `groups="base.group_erp_manager"` |
| `display_aws_secret_access_key` | Char | Masked mirror, see the protected-field pattern below. |
| `aws_region` | Selection | Required, default `eu-central-1`. Frankfurt / Ireland / N. Virginia / Oregon / Singapore. |
| `aws_s3_bucket_prefix` | Char | Default `oduist-connect-`. The IAM policy is scoped to it; settable to match an existing naming convention. |
| `aws_s3_bucket` | Char | Bucket name or bare suffix as typed by the admin. |
| `aws_s3_bucket_name` | Char, compute | `prefix + name`, the actual bucket used everywhere. |
| `aws_s3_prefix` | Char | Folder inside the bucket, default `recordings`. |
| `s3_retention_days` | Integer | `0` = keep forever; `>0` installs a lifecycle rule. |
| `aws_s3_url` | Char, compute | Ready to paste into the Twilio Console. |
| `aws_iam_policy` | Text, compute | The JSON policy to attach to the IAM user. |
| `twilio_aws_credential_sid` | Char, readonly | `CR…` SID once the credential exists. |

**Protected-field masking.** `aws_secret_access_key` follows the established
pattern: the real value carries `groups="base.group_erp_manager"`, the UI binds
to `display_aws_secret_access_key`, and `write()` copies the typed value across
and overwrites the display field with asterisks. `connect_s3` declares its own
`S3_PROTECTED_FIELDS = ["display_aws_secret_access_key"]` and its own `write()`
override, exactly as `connect_twilio` does with `TWILIO_PROTECTED_FIELDS` — the
core `PROTECTED_FIELDS` list is not touched.

**Computes**

| Method | Description |
|--------|-------------|
| `_compute_aws_s3_bucket_name()` | `normalize_bucket_name(aws_s3_bucket, _effective_s3_prefix())` |
| `_compute_aws_s3_url()` | `build_s3_url(aws_s3_bucket_name, aws_region, aws_s3_prefix)`; False when bucket or region is missing |
| `_compute_aws_iam_policy()` | `build_iam_policy(_effective_s3_prefix())` |
| `_effective_s3_prefix()` | `aws_s3_bucket_prefix or S3_BUCKET_PREFIX` |

**Methods**

| Method | Description |
|--------|-------------|
| `_get_s3_client()` | boto3 S3 client built from the singleton settings under `sudo()` (the secret is `group_erp_manager`-restricted). `import boto3` is done inside the method so the module still loads when boto3 is absent. |
| `action_provision_s3_bucket()` | `create_bucket` (with `LocationConstraint` except in `us-east-1`) → `put_public_access_block` (all four blocks on) → `put_bucket_encryption` (AES256) → `put_bucket_lifecycle_configuration` when `s3_retention_days > 0`. Idempotent: `BucketAlreadyOwnedByYou` / `BucketAlreadyExists` are tolerated. An `AccessDenied` is re-raised with a message naming the prefix and the exact ARN the policy needs, because a prefix mismatch is the common failure. |
| `action_create_twilio_aws_credential()` | `GET https://accounts.twilio.com/v1/Credentials/AWS`; if a credential named `connect-s3-recordings` exists, adopt its SID; otherwise `POST` with `Credentials=<key>:<secret>` and store the returned `CR…` SID. Idempotent. |
| `action_recreate_twilio_aws_credential()` | Delete the existing `connect-s3-recordings` credential and create a fresh one from the current AWS keys — Twilio cannot update a credential's key in place. The new SID must be re-selected in the Console, so the notification is sticky. Guarded by a `confirm=` on the button. |
| `_twilio_auth()` | Internal: the `(account_sid, auth_token)` pair for the Twilio accounts API, or raise when unset. |
| `_aws_credentials_or_raise()` | Internal: the `(access_key, secret)` pair, or raise when either is missing. |
| `_create_twilio_credential()` / `_list_twilio_credentials()` / `_delete_twilio_credential()` | Internal wrappers around `accounts.twilio.com/v1/Credentials/AWS` (POST / GET / DELETE) used by the two credential actions. |
| `open_s3_form()` | Returns the act_window for the module's own settings form, following `connect_memory.open_memory_form()`. |

The Twilio account credentials these actions use (`account_sid`, `auth_token`)
live on `connect_twilio`'s `connect.settings` extension — available because of
the hard dependency.

### 3. `recording.py` — `_inherit = 'connect.recording'`

**Fields**

| Field | Type | Notes |
|-------|------|-------|
| `recording_expired` | Boolean, compute | Non-stored. Gates on `_s3_object()` first: a recording that does not live in our bucket (pre-switch Twilio, attachment) **never** reports expired, whatever the retention setting. For S3-hosted audio it is `is_recording_expired(start_time, s3_retention_days, now)` — pure arithmetic, never calls S3. |

**Methods**

| Method | Description |
|--------|-------------|
| `_s3_object()` | Return `(bucket, key)` when this recording's audio lives in our bucket, else `()` (attachment present, S3 disabled, or a non-S3 `media_url`). The single predicate every S3 read path branches on. |
| `_fetch_media_to(temp_file)` | Override of the core seam. When `_s3_object()` matches, `download_fileobj(bucket, key, temp_file)`; otherwise `super()` (attachment or `requests.get`). |
| `_get_media_src(proxy_recordings)` | Override of the core seam. With `proxy_recordings` off and an S3 URL, return a boto3 presigned URL; otherwise `super()`. |
| `_get_recording_widget()` | Override: call `super()`, then replace the widget with `<i>Recording expired</i>` for records where `recording_expired` is set. |

The recording row — transcript, summary, price, partner links — is **kept** when
the audio expires; only the audio is gone.

---

## Core seams added in `connect` (connect/models/recording.py)

The old implementation lived inside the core module and needed no seams. Here
the S3 code lives outside `connect`, so two blocks are extracted into
overridable methods. Both are pure extract-method refactors: no behavior change,
no `release.version_info` branching, so the "Python source identical across
series branches" invariant is unaffected.

| Seam | Extracted from | Default behavior |
|------|----------------|------------------|
| `_fetch_media_to(temp_file)` | `transcribe_recording()` | Write `recording_attachment` bytes if present, else stream `media_url` with `requests.get(..., timeout=30)`. |
| `_get_media_src(proxy_recordings)` | `_get_recording_widget()` | Attachment URL, else `/connect/recording/<id>` when proxying, else the raw `media_url`, else `''`. |

Without these, `connect_s3` would have to copy both methods wholesale and drift
from core on every future change.

---

## Controllers — connect_s3/controllers/main.py

`class ConnectS3Controller(ConnectController)` — inherits the core controller
from `odoo.addons.connect.controllers.main` and overrides one method.

| Method | Description |
|--------|-------------|
| `_serve_media(media_url)` | When S3 is enabled and the URL is ours: `get_object` and stream the bytes with the object's `ContentType` (fallback `audio/mpeg`) and a `Content-Disposition` built from the key's basename. `NoSuchKey` → HTTP **410 Gone**, the safety net for a lifecycle deletion that `recording_expired` has not predicted (retention changed after the fact). Anything else falls through to `super()`. |

This covers both existing core routes, `/connect/recording/<id>` and
`/connect/voicemail/<id>`, since both funnel through `_serve_media`.

### The Twilio-hosted (mixed-mode) path

Pre-switch recordings still live at `api.twilio.com` and need HTTP basic auth
with `account_sid` / `auth_token`. There is **no controller subclass in
`connect_twilio`** for this; the seam is a settings method: core
`ConnectController._serve_media()` (`connect/controllers/main.py`) asks
`connect.settings.get_media_auth(media_url)` for credentials before its
`requests.get`, and `connect_twilio` overrides that method
(`connect_twilio/models/settings.py`) to return `(account_sid, auth_token)` for
`*.twilio.com` hosts only — an External Storage bucket URL must never receive
the Twilio token. `ConnectS3Controller._serve_media` simply falls through to
`super()` for non-S3 URLs, which picks up that auth (ADR-060).

---

## Views — connect_s3/views/settings.xml

- `ir.actions.server` `s3_settings_action` → `action = model.open_s3_form()`
- `menuitem` `s3_settings_menu`, `parent="connect.menu_connect_settings"`,
  `groups="connect.group_admin"`, name **S3 Storage**, `sequence="1200"`
- `connect_s3_settings_form` — a standalone `connect.settings` form
  (`create="false" delete="false"`), not a page injected into the core form, per
  the architecture rule that each module ships its own settings view.

Form layout — a numbered path, since the order genuinely matters:

1. **Bucket prefix** — `aws_s3_bucket_prefix` (the IAM policy below is scoped to it)
2. **IAM policy** — `aws_iam_policy` read-only in an `ace` widget, plus the AWS
   Console steps for creating the IAM user and attaching the policy
3. **Access key** — `aws_access_key_id`, `display_aws_secret_access_key`
   (`password="1"`), `aws_region`, `aws_s3_bucket`, `aws_s3_bucket_name`
   (readonly), `aws_s3_prefix`, `s3_retention_days`
4. **Provisioning** — `action_provision_s3_bucket` (primary),
   `action_create_twilio_aws_credential`, `action_recreate_twilio_aws_credential`
   (with `confirm=`)
5. **Values to paste** — `twilio_aws_credential_sid`, `aws_s3_url`, both readonly
6. **Twilio Console checklist** — Voice → Recordings → Settings → enable external
   S3 → pick credential `connect-s3-recordings` → paste the S3 URL → Save → only
   then tick *Store recordings in S3* here

Everything below the master flag is `invisible="not s3_recordings_enabled"`.

---

## Security

No new models, therefore no `ir.model.access.csv`. Access is controlled by:

- the menu and the settings form: `connect.group_admin`
- `aws_secret_access_key`: `groups="base.group_erp_manager"` plus display masking
- the bucket itself: public access blocked on all four axes, SSE-S3 at rest
- the IAM user: least-privilege policy scoped to `arn:aws:s3:::<prefix>*`

---

## Tests — connect_s3/tests/

| File | Covers |
|------|--------|
| `test_s3_utils.py` | Every `s3_utils` function without a database: prefix normalization idempotence and blank handling, IAM policy ARNs tracking a custom prefix, URL building with and without a folder prefix, S3-vs-Twilio URL detection, key parsing for virtual-hosted and path-style URLs, lifecycle config shape, expiry arithmetic including the `retention_days = 0` case. |
| `test_s3_settings.py` | `aws_s3_bucket_name` and `aws_s3_url` computes, `aws_iam_policy` following `aws_s3_bucket_prefix`, and the `display_aws_secret_access_key` masking round-trip. |
| `test_s3_recording.py` | 11 tests over the read path with a stubbed S3 client: `recording_expired` arithmetic and its `_s3_object()` gating (Twilio-hosted and disabled-S3 recordings never expire, attachments never go to S3), the expired widget text, `_get_media_src` returning a presigned URL vs falling through (Twilio URL, proxy setting, S3 disabled), and `_fetch_media_to` downloading from the stub. |

No test contacts AWS or Twilio — the boto3 client is stubbed.

---

## Documentation

- `connect_s3/docs/index.md` — module overview (what it does, mixed mode,
  expiry indicator)
- `connect_s3/docs/setup.md` — the full setup walkthrough: AWS IAM user and
  policy, Odoo settings, the manual Twilio Console step
- `connect_s3/mkdocs.yml` — per-module docs config
- root `mkdocs.yml` — an `!include ./connect_s3/mkdocs.yml` entry in `nav`
- `requirements.txt` — `boto3`

---

## Known limitation: the S3 key format is not confirmed live

`parse_s3_key` was written against Twilio's *documented* behavior, not against
an observed object. The original research (old repo, `connect_addons`) recorded
this as an open item: the test account's External S3 toggle never took effect,
so the exact `RecordingUrl` and key layout Twilio writes were never seen. The
parser is deliberately permissive — it accepts both S3 URL styles and falls back
to the raw path — but it has not been validated end to end.

Closing this requires a live run: real AWS keys, a real bucket, the Console
toggle flipped, and a recorded call. Until that happens, treat the read path as
**unverified against production Twilio**, and expect `parse_s3_key` to be the
first thing to adjust if playback 404s.

---

## Verification plan

- unit tests (above), no network
- module installs and upgrades cleanly in an oduflow environment
- the **S3 Storage** menu appears under Connect → Configuration for an admin and
  the settings form opens

Explicitly out of scope for this round: any call against AWS or the Twilio
accounts API. There is therefore no end-to-end proof that a recording lands in
the bucket and plays back — see the known limitation above.
