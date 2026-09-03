# S3 Recording Storage

Store Twilio call recordings in your own AWS S3 bucket instead of Twilio's
cloud. You own the retention policy, and Twilio stops billing you for storage.

## How it works

This builds on Twilio's **External S3 Storage** feature. Once it is switched on,
Twilio writes each recording straight into your bucket and the URL it sends Odoo
points at S3. Odoo never uploads anything — it provisions the bucket, creates
the credential Twilio uses, and reads the audio back for playback, proxy
download and transcription.

Two consequences worth knowing before you start:

- **Recordings made before the switch stay on Twilio.** They keep playing
  normally; there is no migration. Both kinds coexist indefinitely.
- **Once external storage is on, the audio is no longer fetchable from Twilio.**
  If the AWS credentials in Odoo stop working, playback stops working.

## What it adds

| Where | What |
|-------|------|
| **Connect → Configuration → S3 Storage** | The whole setup: bucket prefix, generated IAM policy, AWS keys, provisioning buttons, and the two values to paste into the Twilio Console. |
| Recording player | Audio streams from your bucket. Once a lifecycle rule deletes a file, the player says **Recording expired** and the transcript and summary are kept. |
| Transcription | OpenAI transcription reads the audio from S3, so summaries keep working after the switch. |

It owns no models of its own: it extends `connect.settings` and
`connect.recording`, and subclasses the core media controller.

See [Setup](setup.md) for the step-by-step, and ADR-060 for the design.
