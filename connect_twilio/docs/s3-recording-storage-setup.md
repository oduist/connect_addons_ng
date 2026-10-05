# Setup

Everything below happens on one page: **Connect → Configuration → S3 Storage**.
Tick *Store recordings in S3* to reveal the settings.

## 1. Create the AWS IAM user

1. Decide on the **S3 Bucket Prefix**. The default `oduist-connect-` is fine;
   change it only to match an existing naming convention. Every bucket name you
   type is forced to start with it, and the IAM policy is scoped to it.
2. Copy the **AWS IAM Policy** shown on the page.
3. In the AWS Console go to **IAM → Users → Create user** (e.g. `connect-s3`).
4. On **Set permissions** choose **Attach policies directly → Create policy →
   JSON**, paste the policy, name it (e.g. `connect-s3-recordings`), create it,
   and attach it to the user.
5. Open the user → **Security credentials → Create access key** → choose
   **Application running outside AWS**. Copy the access key ID and the secret.

The policy grants only bucket create/configure and object read/write under your
prefix. It contains no `iam:*` permissions.

## 2. Fill in the Odoo settings

| Field | What to enter |
|-------|---------------|
| AWS Access Key ID | from step 1 |
| AWS Secret Access Key | from step 1 (stored masked, visible only to system administrators) |
| AWS Region | where the bucket should live |
| S3 Bucket Name | a name or bare suffix; the prefix is prepended automatically |
| Full Bucket Name | read-only, this is the bucket that actually gets created |
| S3 Folder (prefix) | folder inside the bucket, default `recordings` |
| Retention (days) | `0` keeps audio forever; any other value installs an S3 lifecycle rule |

Then press **CREATE / CONFIGURE S3 BUCKET**. This creates the bucket, blocks all
public access, turns on SSE-S3 encryption at rest, and installs the lifecycle
rule if you set a retention. It is safe to press again — re-running re-applies
the configuration to an existing bucket.

If AWS answers *AccessDenied*, the IAM policy's `Resource` ARN does not match
your prefix. The error message names the exact ARN to allow.

Next press **CREATE TWILIO AWS CREDENTIAL**. Odoo registers your AWS key with
Twilio under the name `connect-s3-recordings` and shows the resulting SID, so
you never paste AWS keys into the Twilio Console. Pressing it again adopts the
existing credential rather than creating a duplicate.

## 3. Switch it on in the Twilio Console

Twilio exposes voice recording settings in the Console only — there is no public
API for them, so this step is manual and one-off.

1. Twilio Console → **Voice → Recordings → Settings**
2. Enable external S3 storage
3. Pick the AWS credential **connect-s3-recordings** (the SID is shown in Odoo)
4. Paste the **S3 URL** shown in Odoo
5. Save
6. Back in Odoo, tick **Store recordings in S3**

Place a test call and confirm the recording plays back from the call record.

## Retention and expired recordings

With a retention of N days, the S3 lifecycle rule deletes the audio file N days
after the recording started. Odoo shows **Recording expired** in the player from
that moment. The recording row itself, along with its transcript and summary, is
kept — only the audio goes.

If a recording's audio is already gone when someone tries to play it, the
download returns HTTP 410 rather than an error page.

## Rotating the AWS keys

Twilio cannot update a stored credential's key. To rotate:

1. Create a new access key for the IAM user in AWS.
2. Enter it in Odoo.
3. Press **RECREATE TWILIO CREDENTIAL**. The old credential is deleted and a new
   one created.
4. **Re-select the new credential in the Twilio Console** (Voice → Recordings →
   Settings). Twilio keeps pointing at the old SID until you do — recordings
   will fail to upload in the meantime.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| *AccessDenied* on provisioning | IAM policy not attached, or its ARN prefix differs from the bucket prefix |
| Playback 404s on new recordings | The S3 key layout differs from what the module expects — see the note in `specs/decisions/060-s3-recording-storage.md` |
| Playback 410s | The lifecycle rule already deleted that audio |
| Old recordings stopped playing | Those are Twilio-hosted; check `account_sid` / `auth_token` in the Twilio settings |
