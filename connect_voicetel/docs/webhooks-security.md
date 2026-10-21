# Webhooks & Security

## Routes

All VoiceML callbacks arrive under `/voicetel/webhook/*` and run as the
dedicated webhook user (`connect.user_connect_webhook`):

| Route | Purpose |
|-------|---------|
| `/voicetel/webhook/domain` | Voice URL of the tenant SIP domains: routes calls placed from registered devices |
| `/voicetel/webhook/number` | Voice URL of the account's numbers |
| `/voicetel/webhook/voiceml/<id>` | Voice URL of a VoiceML app |
| `/voicetel/webhook/callstatus` | Call status callbacks (initiated/ringing/answered/completed) |
| `/voicetel/webhook/<model>/call_action/<id>` | `<Dial>` action of a user or call flow |
| `/voicetel/webhook/callflow/<id>/gather` | `<Gather>` action of a call flow |
| `/voicetel/webhook/recordingstatus` | Recording status callbacks |
| `/voicetel/webhook/vm_recordingstatus` | Voicemail recording callbacks |
| `/voicetel/webhook/outgoing_callerid` | Caller-ID verification result |
| `/voicetel/webhook/message` | Inbound messages and delivery receipts |

## Signature validation

VoiceML signs every callback and every voice URL fetch with the
`X-Twilio-Signature` header: an HMAC-SHA1 of the URL as transmitted plus the
sorted POST parameters, keyed with the account **API key**. The module
validates it with the Twilio helper's `RequestValidator` while **Verify
VoiceTel Requests** is on (default). Requests that fail validation are
answered with a spoken "Invalid VoiceTel request" and are not processed.

The validated URL is the HTTPS form of the request URL, query string
included. Keep the Connect **API URL** equal to the public address VoiceML
calls; a reverse proxy that rewrites the host or path breaks validation.

## Recordings

Recording callbacks download the audio into Odoo immediately, with the
account credentials: VoiceML keeps the file only until it is archived to
the tenant's own bucket or cleaned up. A recording that could not be
fetched in time keeps its URL and is proxied with the credentials for as
long as VoiceML serves it. The API key is never sent to a bucket URL.

## Access groups

| Group | Access |
|-------|--------|
| **Connect User** | Read access to numbers, extensions, call flows, caller IDs, VoiceML apps and SIP domains; their own SIP password through the browser phone |
| **Connect Administrator** | Full access, settings, message configuration |
| **Webhook user** | Read access needed to route calls; write access on outgoing caller IDs for the verification callback |

The API key is stored on a field restricted to the Settings manager group
and is never returned to the webhook user or over RPC.
