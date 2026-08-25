# 060 — S3 recording storage as a Twilio add-on (`connect_s3`)

## Problem

The old monolithic `connect_addons` generation stored Twilio call recordings in
a customer-owned AWS S3 bucket, with the whole feature living **inside core
`connect`**: `s3_utils.py`, ~14 AWS fields plus three provisioning actions on
`connect.settings`, an S3 branch in `connect.recording` and in the
`_serve_media` controller, and an "S3 Storage" notebook page on the core
settings form.

In `connect_addons_ng` (ADR-031) core `connect` is technology-agnostic: it must
not reference Twilio concepts, must not hold PBX configuration, and must not
grow a `boto3` dependency for one provider's storage feature. Porting the
feature therefore had to decide **what shape it takes** here — which is not the
same question as where the files go, because the underlying mechanism is not
provider-neutral.

The mechanism matters: this is Twilio's *External S3 Storage* feature. Once it
is enabled on the account, **Twilio writes the audio into the bucket itself**
and the `RecordingUrl` Twilio delivers points at S3 instead of `api.twilio.com`.
Odoo never uploads. It configures the bucket, creates the Twilio-side AWS
credential, and reads the media back. Twilio's own docs are explicit that after
the switch the media can no longer be fetched from Twilio.

## Options

1. **Twilio add-on** — a `connect_s3` module depending on `connect` +
   `connect_twilio`, porting the existing behavior as-is.
2. **Provider-agnostic offload** — `connect_s3` depends on `connect` only; a
   cron pulls each recording from whatever provider produced it (`media_url` or
   `recording_attachment`) and uploads it to S3, after which playback and
   transcription read from S3. Works for Twilio, Telnyx, FreeSWITCH, Asterisk,
   Infobip and LiveKit alike.
3. **Both** — an agnostic `connect_s3` plus a thin `connect_s3_twilio`
   sub-module carrying the Twilio credential API and the Console instructions.

## Decision

**Option 1.** The feature being ported *is* the Twilio external-storage
integration, not a generic offload. Every asset it carries is Twilio-shaped: the
`connect-s3-recordings` AWS credential created through
`https://accounts.twilio.com/v1/Credentials/AWS`, the S3 URL formatted for the
Twilio Console field, the Console checklist, and the mixed-mode read path that
distinguishes an S3 `RecordingUrl` from an `api.twilio.com` one. Rebuilding it
as Option 2 would not be a port; it would be a different feature — Odoo becomes
the uploader, needs a work queue, retry and back-pressure handling, and doubles
egress by pulling every recording through the Odoo worker.

Option 2 remains the right answer if S3 storage is ever wanted for the other
providers, and nothing here blocks it: `s3_utils.py` is already free of Odoo,
boto3 and Twilio, and would carry over unchanged. Option 3 was rejected as
premature — it pays the cost of a module split for a second consumer that does
not exist.

`connect_s3` therefore depends on `['connect', 'connect_twilio']` and declares
`boto3` in `external_dependencies`, keeping that dependency off both core and
`connect_twilio`.

## Consequences

- **S3 recording storage is Twilio-only.** Installing `connect_s3` alongside
  FreeSWITCH, Asterisk, Telnyx, Infobip or LiveKit does nothing for their
  recordings. This matches the mechanism — those providers do not write to the
  customer's bucket.
- **No new models.** The module extends `connect.settings` and
  `connect.recording` and subclasses the core controller, so it ships **no**
  `ir.model.access.csv`. UI access is gated on `connect.group_admin`;
  `aws_secret_access_key` additionally carries `groups="base.group_erp_manager"`
  with the established display-field masking (its own `S3_PROTECTED_FIELDS`
  list, not an addition to core's).
- **Two seams are added to core `connect.recording`:**
  `_fetch_media_to(temp_file)` extracted from `transcribe_recording()`, and
  `_get_media_src(proxy_recordings)` extracted from `_get_recording_widget()`.
  Both are pure extract-method refactors with no behavior change and no
  `release.version_info` branching, so the "Python identical across series
  branches" invariant holds. The alternative — copying both methods wholesale
  into `connect_s3` — would drift from core on every future change.
- **Mixed mode is permanent.** Recordings created before the Console toggle stay
  on Twilio and are read the old way; there is no migration. This also means the
  Twilio read path must keep working, which exposed a pre-existing gap: core
  `_serve_media` fetches `media_url` with a bare `requests.get` and no auth,
  while Twilio recording URLs require basic auth with `account_sid` /
  `auth_token`. `connect_twilio` gains its own `_serve_media` override supplying
  that auth; `connect_s3` falls through to it.
- **The Twilio toggle stays manual.** Twilio's public API exposes
  `RecordingSettings` for **video only**; for voice, external S3 storage is
  Console-only (Voice → Recordings → Settings). Odoo cannot flip it, so the
  module instead surfaces the two values to paste and a numbered checklist.
- **Retention is delegated to S3.** A lifecycle rule expires the audio after
  `s3_retention_days`; a computed `recording_expired` (pure date arithmetic, no
  S3 call) shows "Recording expired" in the player, and a `NoSuchKey` on read
  returns HTTP 410 as the safety net. The recording row, transcript and summary
  are kept — only the audio goes.
- **SSE-KMS, S3-compatible stores and bulk migration of existing Twilio-hosted
  recordings are out of scope.** SSE-S3 needs no key administration; a custom
  `endpoint_url` would point at a store Twilio cannot write to; mixed mode
  already keeps old recordings playable.

## Open risk carried over from the original design

`parse_s3_key()` was written against Twilio's documented behavior, **not against
an observed object**. The original research recorded this explicitly: the test
account's External S3 toggle never took effect, so the exact `RecordingUrl` and
key layout Twilio writes were never seen. The parser is deliberately permissive
(both virtual-hosted and path-style URLs, raw-path fallback), but the read path
is **unverified against production Twilio**. Closing this needs a live run with
real AWS keys, the Console toggle flipped and a recorded call; `parse_s3_key` is
the first thing to adjust if playback 404s.
