# ADR-050: Core OpenAI transcription and summary pipeline

**Status:** Accepted
**Date:** 2026-08-16

> Consolidates four decisions on the same pipeline — summary model selection,
> transcription queue idempotency, call analysis retention and the estimated
> transcription price — that were first drafted as separate records. Each is
> kept below as its own dated section.

## Context

Core call analysis is provider-agnostic: `connect.recording` stores the audio
reference, the OpenAI transcript and the generated summary, `connect.call`
carries the durable copy shown to users, and `cron_transcribe_recordings`
performs the work outside the provider webhook transaction.

Four properties of that pipeline are configuration or lifecycle decisions rather
than implementation details: which model produces the summary, when a queued
recording may be sent to OpenAI a second time, how long the audio must be kept
once the analysis exists, and what the stored cost figure actually means.

## Decision 1 — Configurable summary model (2026-08-16)

Summarization was hard-coded to `gpt-4o` unless the deployment set the
undocumented `OPENAI_COMPLETION_MODEL` environment variable, so administrators
could neither see nor change the active model.

Add a required `openai_summary_model` selection to `connect.settings`:

- `gpt-5.4-mini` (GPT-5.4 mini), selected by default;
- `gpt-4o` (GPT-4o), retained for existing workflows that need the previous
  model.

The selection is shown on the core Transcription settings tab and is used by
`connect.recording.make_summary()`. `OPENAI_COMPLETION_MODEL` remains an
optional deployment-level override and takes precedence when set, preserving
existing hosted configuration.

GPT-5-family Chat Completions use `max_completion_tokens`; legacy models keep
the existing `max_tokens` and sampling parameters, so legacy-only parameters are
never sent to GPT-5.4 mini and GPT-4o behavior is unchanged.

## Decision 2 — Idempotent transcription queue (2026-08-16)

Creating a recording while automatic transcription is enabled sets
`transcription_pending`. Manual transcription and the transcript callback
completed the transcript without clearing that flag, so enabling the scheduled
action later re-sent an already transcribed recording to OpenAI and paid for it
twice. This is most visible in sanitized development databases, where scheduled
actions are disabled while recordings keep being queued.

- Every completed transcription attempt clears `transcription_pending`, whether
  it succeeds or stores a transcription error.
- Transcript callback updates also clear `transcription_pending`.
- The transcription cron treats an existing transcript as completed work: it
  clears the stale queue flag without calling OpenAI again.
- The cron remains a normal Odoo scheduled action. Environment sanitization may
  disable it, and administrators must reactivate it when automatic background
  processing is required in that environment.

Failed attempts keep their existing single-attempt behavior: the error is stored
and the queue flag is cleared rather than retried indefinitely.

## Decision 3 — Call analysis retained independently of the recording (2026-08-16)

The summary was copied to `connect.call`, but the call transcript was only
computed from the latest recording. Deleting a recording therefore destroyed the
transcript, and could also lose the summary when it had not been synchronized.
Some deployments must discard call audio immediately after AI processing while
keeping the analysis as part of the call ledger.

- Store `transcript` permanently on `connect.call`, alongside the existing
  stored `summary` field.
- Keep the recording transcript and summary fields for provider compatibility,
  but synchronize both values from the latest analyzed recording to the linked
  call whenever the recording or its call link changes. The call fields are the
  durable copy used by the call form.
- Add the disabled-by-default `delete_recording_after_transcription` core
  setting on the Transcription tab.
- After a successful transcription and summary workflow, delete the
  `connect.recording` row when the option is enabled and the recording is linked
  to a call. Successful means that a non-empty transcript was stored and no
  transcription or summary error was returned.
- Keep recordings without a linked call. Deleting them would still destroy the
  only durable copy of their analysis.
- Backfill each call's transcript from its latest recording with a non-empty
  transcript. Backfill summaries only when the call does not already have one.

Provider-side media is not deleted by this option. It removes the Odoo recording
row and any Odoo-managed attachment; provider retention remains a provider
configuration concern.

## Decision 4 — Estimated OpenAI transcription price (2026-08-16)

`connect.recording.transcription_price` was written only by the legacy
transcript callback, which rounded to two decimals and therefore stored zero for
normal short Whisper calls.

- Calculate the price from the billable usage seconds returned by OpenAI,
  falling back to the response duration when usage is unavailable; do not use
  provider recording metadata.
- Use the published Whisper rate of USD 0.006 per minute for the existing
  `whisper-1` request.
- Store the estimate with up to six decimal places, and apply the same
  precision-preserving formatting to callback-provided prices.
- Keep `transcription_price` as a `Char` field for compatibility with existing
  databases and provider adapters. A missing price is stored as false rather
  than the literal string `None`.
- Treat the field as the speech-to-text estimate only; summary-model token cost
  is outside its scope.

The value remains an estimate based on the published rate; the OpenAI invoice
stays authoritative, and a future transcription model change must update the
model and its rate together.

## Consequences

- New and upgraded databases default call summaries to GPT-5.4 mini, and
  administrators can switch models without touching the service environment.
  Deployments that already set `OPENAI_COMPLETION_MODEL` keep overriding the UI
  selection until that variable is removed.
- Manual and callback-driven transcription cannot later be duplicated by the
  automatic queue; existing stale pending rows are repaired on the next cron run.
- Audio retention can be reduced without losing call analysis. The recording
  list no longer contains auto-deleted rows while the call form still shows the
  transcript and summary, and failed processing stays inspectable and retryable.
- A 30-second Whisper transcription is stored as `0.003` instead of being
  rounded to zero, on the direct, automatic and manual paths alike.
- All four decisions stay inside existing core models and the admin-only
  `connect.settings`; no new model or access-control decision is introduced.
