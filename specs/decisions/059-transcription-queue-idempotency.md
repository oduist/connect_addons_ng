# ADR-059: Keep the transcription queue idempotent

## Context

Automatic recording transcription is deferred to the
`cron_transcribe_recordings` scheduled action. Creating a recording while
automatic transcription is enabled sets `transcription_pending`, and the cron
later sends the audio to OpenAI outside the provider webhook transaction.

A recording can also be transcribed manually with the **Transcribe** button or
updated through the transcript callback. Those paths completed the transcript
without clearing `transcription_pending`. If the scheduled action was enabled
later, it processed the already-transcribed recording again and incurred a
second OpenAI request.

This is particularly visible in sanitized development environments, where Odoo
scheduled actions are disabled while recordings can still be queued.

## Decision

- Every completed transcription attempt clears `transcription_pending`, whether
  it succeeds or stores a transcription error.
- Transcript callback updates also clear `transcription_pending`.
- The transcription cron treats an existing transcript as completed work: it
  clears the stale queue flag without calling OpenAI again.
- The cron remains a normal Odoo scheduled action. Environment sanitization may
  disable it, and administrators must reactivate it when automatic background
  processing is required in that environment.

## Consequences

- Manual and callback-driven transcription cannot later be duplicated by the
  automatic queue.
- Existing stale pending rows with transcripts are repaired safely the next
  time the cron runs.
- Failed attempts keep their existing single-attempt behavior: the error is
  stored and the queue flag is cleared rather than retried indefinitely.
