# connect_voiceml — live test runbook

How to take the scaffold from "installed" to "a call ran through VoiceML
end to end". This is the acceptance pass that decides whether
the provider is worth polishing further.

## 0. Prerequisites

- An Odoo 19.0 instance with `connect` installed and a database with the
  `voiceml` python package available (`pip install voiceml`).
- A VoiceML tenant: an `AccountSid` and an API key. The API
  key is both the REST auth token and the webhook `X-Twilio-Signature` key.
- The VoiceML OpenSIPS registrar's public `wss://` URL (see below).

## 1. Install

```
# in the Odoo addons path, on the branch feature/connect_voiceml
ln -s /path/to/connect_addons_ng/connect_voiceml <addons>/connect_voiceml
# restart Odoo, then:
./odoo-bin -d <db> -i connect_voiceml --stop-after-init
```

The module depends on `connect`; install both together if needed.

## 2. Configure

Connect → VoiceML → Configuration → Settings:

| Field | Value |
|---|---|
| Account SID | the tenant `AC…` |
| API Key | the tenant API key |
| VoiceML API URL | `https://voiceml.voicetel.com` |
| WebRTC WSS URL | `wss://<node>:8443` |

Node public IPs (from the OpenSIPS design doc):
`east-1` 3.220.193.70, `east-2` 3.12.226.65, `west-1` 52.9.10.85. OpenSIPS
listeners: SIP 7060 (UDP/TCP), TLS 7061, **WSS 8443**, WS 8442.

Then click **SYNC VOICEML ACCOUNT**. Expect: TwiML applications, a SIP domain
+ credential list (bound for registration and call auth), phone numbers and
outgoing caller IDs created on the VoiceML side.

## 3. Provision a user

Connect → Users → open a user → **VoiceML** tab:

1. Set **SIP Phone Enabled** / **Web Phone Enabled**.
2. Set **Username** (alphanumeric) and a **Domain**.
3. Set a **Password** — this provisions a SIP credential in the domain's
   credential list.

## 4. Register a softphone

Either the built-in phone (systray → Phone, once `jssip.min.js` is in the
bundle) or any standalone SIP/WebRTC client (Bria, Zoiper, MicroSIP) using:

- **Registrar / WSS**: `wss://<node>:8443` (WebRTC) or `sip:<node>:7060` (UDP/TCP) / TLS 7061
- **Username**: the user's `username`
- **Password**: the user's `password`
- **Domain / realm**: the SIP domain `domain_name`

A successful registration proves the SIP Domain + CredentialList +
OpenSIPS registrar chain works.

## 5. Click-to-call (outbound)

From the CRM (or `connect.settings.originate_call`), call a number. Expected:

1. The agent's softphone rings (VoiceML originates `sip:username@domain` and
   runs the TwiML that `<Dial>`s the customer number).
2. `connect.call` / `connect.channel` rows appear, driven by the
   `voiceml/webhook/callstatus` callbacks.
3. If `record_calls`, a recording row appears via
   `voiceml/webhook/recordingstatus`.

## 6. Inbound

Call the tenant's number. Expected: `voiceml/webhook/number` routes to the
configured destination (user / callflow / application).

## 7. What to watch on the VoiceML side

- Node journal: `journalctl -n 200` for the TwiML fetch,
  originate and callback lines.
- The SIP credential must appear under the domain's credential list.

## Known gaps (do not block the pass, but expect them)

- OutgoingCallerIds/ValidationRequests use raw HTTP (the SDK does not wrap
  them yet).
- No WhatsApp, no account balance.
- Softphone is register + answer + audio only (no keypad/transfer UI yet).
