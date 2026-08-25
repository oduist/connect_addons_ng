# Recordings & Transcriptions

## Call Recordings

If call recording is enabled for your account, calls are automatically recorded. Recordings appear:

- **On the call record** — Inline audio player in the call form
- **In the recordings list** — Navigate to **Connect > Calls > Recordings**

### Playback

Click the play button on any recording to listen in your browser. You can also download recordings for offline access.

Caller and called numbers use the standard phone control on an individual
recording form, so a dialable number can be used for click-to-call there. The
recording list shows those numbers as plain text.

### Recording Settings

Recording can be enabled at multiple levels (configured by your administrator):

- **Per user** — Enable/disable recording for a specific PBX user
- **Per call flow** — Enable/disable recording for calls through a specific callflow

The per-user setting also applies to outgoing calls placed from that user's
Telnyx web phone or SIP phone.

### In-Call Recording Control

When runtime recording control is available for your phone provider, the phone
widget shows a recording button during an active call. Use it to start or stop
recording for that call.

The button reflects what the phone system reports for the call, not what the
settings would have done. Recording started automatically by a call flow, by
the per-user **Record Calls** option, or manually from the phone all show the
same active state, and stopping the recording stops whichever of them is
running.

A purple circular badge with a white dot and **REC** means nothing is being
recorded and the button will **start** a manual recording. A purple stop icon
appears only while a recording is actually running and will **stop** it. The
manual button remains available when **Record Calls** is disabled for the user;
that setting controls automatic recording, not whether a specific call may be
recorded manually.

## AI Transcription

When transcription is enabled, recordings are automatically processed:

1. **Speech-to-text** — Audio is sent to OpenAI Whisper for transcription
2. **Summarization** — The transcript is sent to the OpenAI model selected by
   your administrator (GPT-5.4 mini by default) for a concise summary

### Viewing Transcripts

The linked call keeps the transcript and summary permanently. On a retained
recording record, you'll also see:

| Field | Description |
|-------|-------------|
| **Transcript** | Full text of the conversation. |
| **Summary** | AI-generated summary of the call. |
| **Transcription Price** | Estimated Whisper speech-to-text cost in USD, based on OpenAI's processed duration. |

The transcript and summary remain available on the linked call even if the
recording is later deleted. The price remains on retained recording records.
Administrators can configure Connect to delete successfully processed
recordings automatically when audio must not be retained.

### Manual Transcription

You can manually trigger transcription by clicking the **Transcribe** button
on a recording record. Once the manual attempt finishes, the recording is
removed from the automatic queue so it is not sent to OpenAI twice.

### Partner Chatter Integration

When **Register Summary** is enabled in settings, call summaries are automatically posted to the partner's chatter feed. This provides a timeline of all call interactions visible on the contact record.

## Browsing Recordings

Navigate to **Connect > Calls > Recordings** to see all recordings in a list view.

The list shows retained recordings with their call, phone numbers, duration,
summary, and date. Successfully transcribed rows may be absent when automatic
recording deletion is enabled. Use the column selector to show or hide the
optional **Partner** and **Users** columns.

| Field | Description |
|-------|-------------|
| **Call** | Link to the associated call record. |
| **Partner** | Linked contact. |
| **Users** | Internal Odoo users who participated in the call. |
| **Duration** | Recording length. |
| **Summary** | Truncated AI summary for quick review. |
| **Date** | Date and time when the recording record was created. |
