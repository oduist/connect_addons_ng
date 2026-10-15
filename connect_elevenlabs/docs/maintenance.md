# Maintenance

## Scheduled jobs

`connect_elevenlabs` ships **no cron jobs**. All ElevenLabs work is synchronous:

- Agent and tool changes sync to ElevenLabs on record save.
- Per-call context and post-call logging happen on inbound webhooks.
- Reconciliation is manual, via the settings buttons (**SYNC**, **SYNC TOOLS**,
  **REGENERATE PROMPTS**, **UNBIND ACCOUNT**).

## Licensing

ElevenLabs is a licensed Oduist module (`connect_elevenlabs` is registered in the
core license module). The license is checked at three points:

- **Agent create / write** — `check_license('connect_elevenlabs', silent=False)`
  raises if the license is invalid, blocking the change.
- **Call render** — `agent.render()` returns a spoken *"Your trial period is
  over. Please buy a license to continue."* message instead of dialling
  ElevenLabs when the license check fails.
- **Feature gates** — `elevenlabs_enabled` on users/recordings, the
  transcription override, and **SYNC** short-circuit when the license check fails
  (silently), falling back to base Twilio behaviour.

The `post_init_hook` refreshes the license status on install. If agents refuse
to save or calls play the trial message, verify the `connect_elevenlabs` license
in the core settings.

## Recordings & transcription

When **Transcript Provider** is set to **ElevenLabs**, `connect.recording`'s
`transcribe_recording` override downloads the recording media and transcribes it
with ElevenLabs Speech-to-Text (`speech_to_text.convert`, model `scribe_v1`,
diarization on), then writes an OpenAI-generated summary. With any other provider
it falls back to the core transcription pipeline. The license is checked first;
without it, the core pipeline is always used.

Post-call webhooks additionally persist the ElevenLabs conversation transcript
and summary directly onto a `connect.recording` (with `skip_transcription`) so
they appear on the call form and downstream hooks (e.g. Oduist Memory) fire —
without re-transcribing audio ElevenLabs already transcribed.

!!! note "OpenAI stays in core"
    OpenAI summarisation lives in core `connect` because it is provider-agnostic.
    Configure the OpenAI key in the core settings, not here.

## How an inbound agent call flows

1. A call arrives on a Twilio number or extension routed to the agent.
2. `connect.twilio.number.render` (or the extension `dst`) calls
   `agent.render()`, which returns TwiML: `<Dial><Sip>` to
   `sip.rtc.elevenlabs.io`. The SIP-URI user part is the called E.164 DID if a
   real number was hit, otherwise the agent's registered **virtual number**. The
   `connect.call` id is handed to ElevenLabs as an `X-Connect-Call-Ref` SIP
   header, and a Twilio-acceptable caller ID is resolved (falling back to the
   default outgoing caller ID).
3. ElevenLabs calls `POST /connect_elevenlabs/conversation_initiation` (agent
   token) to fetch dynamic variables — partner data, previous-conversation
   summary, users directory, published extensions, language override.
4. The agent runs the conversation, calling server tools as needed (transfer,
   create partner, calendar), each authenticated by the agent token.
5. When the call ends, ElevenLabs calls `POST /connect_elevenlabs/post_call`
   (HMAC-verified), which creates/dedupes a `connect.call` and a
   `connect.recording` with the transcript and summary.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Agent will not save / *license* error | Verify the `connect_elevenlabs` license in core settings. |
| Call plays *"trial period is over"* instead of connecting | Same — the license check failed at render time. |
| Agent answers but has no caller context | Confirm the conversation-initiation webhook is pushed (run **SYNC**), the agent token matches, and the core **API URL** is your public HTTPS URL. Initiation errors return empty variables, not an error. |
| Post-call logs *"no webhook secret configured; run ElevenLabs sync"* | The post-call webhook/secret is missing — run **SYNC** to (re)create it. |
| Post-call **401** / *HMAC signature mismatch* | The stored secret no longer matches ElevenLabs, the timestamp is >30 min old, or the body was altered by a proxy. Re-run **SYNC**. |
| Server tool returns **401 Unauthorized** | The `x-elevenlabs-agent-token` header does not match the setting — run **SYNC** to re-push the token to the workspace and tools. |
| Agent can't transfer / *no public extension* | Mark the target `connect.twilio.exten` as **Published**; only published extensions are offered to the AI. |
| ElevenLabs never calls the initiation webhook | The agent platform settings must enable conversation-initiation client data from webhook; re-save/sync the agent. |
| TTS prompts fall back to Twilio `<Say>` | Integration disabled, no **Selected Voice**, or a TTS generation error — check the API key and voice, then **REGENERATE PROMPTS**. |
| Illegal header value / API key rejected | A stray space in the pasted API key; the client strips whitespace, but re-paste the key cleanly and **SYNC**. |
| Switching to a new ElevenLabs account | Use **UNBIND ACCOUNT** to clear local agent/tool IDs, set the new key, then **SYNC**. |

### Where to look

- **Odoo server log** — the controllers and models log token/HMAC failures and
  ElevenLabs API exceptions under the `connect_elevenlabs` loggers.
- **`connect.debug`** — the core debug model records the routing TwiML and
  transfer TwiML.
- **ElevenLabs dashboard ▸ Conversational AI** — the authoritative record of what
  ElevenLabs sent and received, including webhook delivery status.
