# ADR-056: Telnyx AI conversation transcript and media sync

## Status

Accepted.

## Context

Telnyx AI Assistants retain three related post-call resources:

- conversation messages, which already contain the assistant transcript;
- conversation insights, which contain the configured summary;
- a Call Recording resource with the completed audio file.

The first implementation synchronized conversation messages and insights into
an idempotent `connect.recording` row, but it did not import the physical call
recording. Its insight webhook parser also expected `conversation_id` and
`insights` fields that are not present in Telnyx's
`call.conversation_insights.generated` envelope. Telnyx instead sends the
result under `data.payload.results` and identifies the call with
`data.payload.call_control_id`.

The periodic conversation reconciliation can recover the transcript, but it
may be disabled in sanitized development databases. Telnyx recording download
URLs are short-lived, so persisting only the signed URL is not sufficient for
durable playback or later processing.

Official references:

- https://developers.telnyx.com/api-reference/call-recordings/list-all-call-recordings
- https://developers.telnyx.com/api-reference/conversations/get-conversation-messages
- https://developers.telnyx.com/api-reference/conversations/get-conversation-insights
- https://developers.telnyx.com/api-reference/call-events/call-conversation-insights-generated

## Decision

Odoo treats Telnyx as the authoritative transcription provider for Telnyx AI
Assistant calls. One `connect.recording` row with `source = telnyx-ai` stores
the conversation transcript, insight summary, and attached MP3.

The insight webhook parser accepts the documented Telnyx event envelope,
resolves the Odoo call by `call_control_id`, obtains the conversation ID from
the linked call, and then runs the idempotent conversation synchronization.
Legacy direct payload shapes remain accepted for compatibility.

After synchronizing the text, Odoo queries the Call Recordings API by
`call_control_id`. It downloads the completed audio immediately and stores it
in `recording_attachment`, because the provider download URL expires. The
Telnyx recording ID is stored separately from the conversation ID so repeated
webhooks and reconciliation runs update the same row without downloading an
already attached file again.

Every create and media update in this path uses the existing
`skip_transcription` contract. A Telnyx AI transcript must never enter the
OpenAI transcription queue, even when global call transcription is enabled.

The five-minute batch remains a repair mechanism for missed or delayed
webhooks. It synchronizes both text and media and is safe to run repeatedly.

## Consequences

- Telnyx AI calls appear in Odoo with durable playback, transcript, and
  summary on one recording row.
- No duplicate OpenAI transcription cost or potentially divergent transcript
  is generated for an already transcribed Telnyx AI call.
- A valid insight webhook imports the conversation immediately; the cron only
  repairs missed or delayed delivery.
- If the recording is not yet visible when the webhook arrives, a later batch
  run attaches it.
- Downloading the MP3 adds bounded network work to synchronization, but avoids
  storing an expiring provider URL as the durable recording.
