# Maintenance

## Scheduled actions

| Action | Interval | Purpose |
|--------|----------|---------|
| **Fetch Call Prices from VoiceML** | 5 minutes | Reads the price of finished calls marked for fetching (requires **Fetch Call Prices**). |

Transcription and summarization of recordings are handled by the core
Connect cron once the audio is stored on the recording.

## Licensing

The module registers with the Oduist license service on installation and
checks the `connect` license before placing calls and sending messages.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Sync fails with an authentication error | Wrong Account SID or API key. Keys are shown once by VoiceTel; rotate and re-enter. |
| "Invalid VoiceTel request" on every call | Signature validation fails: the Connect **API URL** differs from the address VoiceML calls, or the API key changed on the VoiceTel side. |
| Browser phone does not register | Check the user's SIP account (enabled, username, domain), the global **Browser Phone** switch, the WebSocket port and that `wss://<label>.<suffix>:<port>` is reachable from the browser. |
| A colleague's extension does not ring | The colleague's SIP account must be enabled; the dialplan rings `sip:<username>@<domain>` and only registered devices answer. |
| Recording plays as 0 seconds | The audio was not downloaded in time and VoiceML no longer serves it. Configure a recording bucket on the VoiceML account so recordings are archived. |
| Caller-ID verification never completes | The verification callback did not reach `/voicetel/webhook/outgoing_callerid`; check the API URL and the webhook user's rights. |

Enable **Connect ▸ Configuration ▸ Debug** to log every webhook payload in
the Connect debug log.
