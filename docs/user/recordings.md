# Recordings & Transcriptions

## Call Recordings

If call recording is enabled for your account, calls are automatically recorded. Recordings appear:

- **On the call record** — Inline audio player in the call form
- **In the recordings list** — Navigate to **Connect > Calls > Recordings**

### Playback

Click the play button on any recording to listen in your browser. You can also download recordings for offline access.

### Recording Settings

Recording can be enabled at multiple levels (configured by your administrator):

- **Per user** — Enable/disable recording for a specific PBX user
- **Per call flow** — Enable/disable recording for calls through a specific callflow

## AI Transcription

When transcription is enabled, recordings are automatically processed:

1. **Speech-to-text** — Audio is sent to OpenAI Whisper for transcription
2. **Summarization** — The transcript is sent to GPT-4o for a concise summary

### Viewing Transcripts

On a recording record, you'll see:

| Field | Description |
|-------|-------------|
| **Transcript** | Full text of the conversation. |
| **Summary** | AI-generated summary of the call. |

The summary also appears on the linked call record.

### Manual Transcription

If automatic transcription is disabled, you can manually trigger it by clicking the **Transcribe** button on a recording record.

### Partner Chatter Integration

When **Register Summary** is enabled in settings, call summaries are automatically posted to the partner's chatter feed. This provides a timeline of all call interactions visible on the contact record.

## Browsing Recordings

Navigate to **Connect > Calls > Recordings** to see all recordings in a list view.

The list shows:

| Field | Description |
|-------|-------------|
| **Call** | Link to the associated call record. |
| **Partner** | Linked contact. |
| **Duration** | Recording length. |
| **Status** | Completed, processing, or failed. |
| **Summary** | Truncated AI summary for quick review. |
| **Player** | Inline audio playback. |
