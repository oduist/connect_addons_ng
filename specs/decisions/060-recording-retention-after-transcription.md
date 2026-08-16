# ADR-060: Retain call analysis independently of recordings

## Status

Accepted.

## Context

`connect.recording` currently stores both the audio reference and the generated
transcript. The summary is copied to `connect.call`, but the transcript on the
call is only computed from the latest recording. Deleting a recording therefore
removes the transcript and can also make the summary unavailable when it was not
successfully synchronized to the call.

Some deployments must discard call audio immediately after AI processing while
retaining the transcript and summary as part of the call ledger.

## Decision

- Store `transcript` permanently on `connect.call`, alongside the existing
  stored `summary` field.
- Keep the recording transcript and summary fields for provider compatibility,
  but synchronize both values from the latest analyzed recording to the linked
  call whenever the recording or its call link changes. Call fields are the
  durable copy used by the call form.
- Add the disabled-by-default `delete_recording_after_transcription` core
  setting on the Transcription tab.
- After a successful transcription and summary workflow, delete the
  `connect.recording` row when the option is enabled and the recording is linked
  to a call. Successful means that a non-empty transcript was stored and no
  transcription/summary error was returned.
- Keep recordings without a linked call. Deleting them would still destroy the
  only durable copy of their analysis.
- Backfill each call's transcript from its latest recording with a non-empty
  transcript. Backfill summaries only when the call does not already have one.

## Consequences

- Audio retention can be reduced without losing call analysis.
- Existing provider integrations may continue writing transcript and summary
  values through `connect.recording`; the core synchronization keeps the call
  ledger current.
- The recording list no longer contains auto-deleted rows, while the call form
  continues to display transcript and summary.
- Failed processing remains inspectable and can be retried because its recording
  is not removed.
- Provider-side media is not deleted by this option. The option removes the Odoo
  recording row and any Odoo-managed attachment; provider retention remains a
  provider configuration concern.
