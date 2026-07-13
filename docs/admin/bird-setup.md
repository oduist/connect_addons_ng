# Bird Integration

The `connect_bird` module connects Odoo to [Bird.com](https://bird.com)
(formerly MessageBird): SMS and WhatsApp messaging (including approved
WhatsApp templates), a call ledger fed by Bird voice events, click-to-call
and call recordings.

## How it works

Odoo talks to the Bird developer platform REST API
(`https://<region>.platform.bird.com/v1`) with an access key
(`bk_<region>_...`); the workspace and region are encoded in the key.
Bird pushes messaging and voice events back to Odoo through **one webhook
endpoint** (`/bird/webhook`), signed per the Standard Webhooks
specification with a secret that Bird issues when the endpoint is
registered.

Click-to-call is a **two-leg callback**: Bird first dials the agent's own
phone number, and once the agent answers, connects the call to the
destination. Bird provides no browser SDK, so there is no web phone — an
agent needs a real phone number (mobile or landline).

Inbound call *routing* (IVRs, queues) stays on the Bird side; Odoo records
the resulting calls in the shared Connect ledger.

## 1. Install the module

Install `connect_bird` like any Odoo addon.

## 2. Create a Bird access key

In your Bird workspace create an access key (`bk_...`) with scopes for
**sms**, **whatsapp**, **voice**, **numbers** and **webhooks**. A key
without these scopes authenticates but receives `403` on the respective
endpoints.

## 3. Configure Connect → Bird → Configuration → Settings

| Setting | Meaning |
|---------|---------|
| Access Key | The `bk_...` key from step 2 (stored masked) |
| SMS Category | Content classification sent with outgoing SMS (default `transactional`) |
| Agent Ring Timeout | How long Bird rings the agent phone on click-to-call |

Click **SYNC BIRD ACCOUNT** — this imports your Bird **numbers** into
*Connect → Bird → Numbers* and your approved **WhatsApp message
templates**.

Mark a number as *Default* if you have several.

## 4. Set up webhooks

Click **SETUP WEBHOOKS**. Odoo registers one webhook endpoint pointing to
`<your Odoo URL>/bird/webhook` and stores the signing secret Bird returns
(it is issued exactly once). The registered endpoint is listed under
*Bird → Configuration → Webhook Endpoints*.

If the access key lacks the webhooks scope (403), register the endpoint
manually in the Bird dashboard with the same URL and paste the `whsec_`
secret into the *Webhook Signing Key* field on the *Development* tab.

!!! warning "Platform limitation"
    As of mid-2026 the Bird platform delivers webhook events for the
    **email product only** — `sms.*`/`whatsapp.*`/`voice.*` events cannot
    be subscribed yet. Until they become available, outgoing message
    delivery statuses are **polled** by the scheduled action
    "Connect Bird: Poll Message Status" (every 5 minutes), and inbound
    messages cannot be received.

Requirements:

- The Odoo **API URL** (Connect → Configuration → Settings) must be a
  public HTTPS URL reachable by Bird.
- Signature verification is on by default; the timestamp tolerance and a
  development-only bypass live on the *Development* tab of the Bird
  settings (visible with developer mode). If the secret is ever lost,
  rotate it on the Bird side and update the *Webhook Signing Key* field.

## 5. Configure users

On each Connect user (Connect → Users):

| Field | Meaning |
|-------|---------|
| Bird Agent Phone | E.164 number Bird dials first on click-to-call |
| Bird Voice Number | Caller ID for click-to-call (default number when empty) |
| Bird Message Number | Default sender for outgoing messages |
| Click-to-call Provider | Set to *Bird* when several telephony modules are installed |
| Messaging Provider | Set to *Bird* when several messaging modules are installed |

## 6. Message routing (optional)

*Bird → Configuration → Message Configuration* maps a Bird number to a
destination model for inbound messages from unknown senders (default:
create a partner). `default_values` is a Python dict literal merged into
the created record.

## Recordings

When *Record Calls* is enabled on the Connect user, click-to-call calls
are recorded by Bird. A scheduled action ("Connect Bird: Fetch Call
Recordings", every 2 minutes) downloads finished recordings into the
Connect ledger — download links are short-lived, so the audio is stored
as an Odoo attachment. Transcription then works exactly like for any
other provider (OpenAI key in core Connect settings).

## Troubleshooting

- **401 in Bird webhook delivery logs** — signing secret mismatch: rotate
  the secret in Bird and update the *Webhook Signing Key* field (or
  delete the endpoint in Bird and re-run **SETUP WEBHOOKS**).
- **403 from the Bird API** — the access key lacks the scope for that
  product (sms/whatsapp/voice/numbers/webhooks): recreate the key with
  the full scope list.
- **WhatsApp message fails immediately** — the 24-hour customer-service
  window is closed: start the conversation with an approved template
  (Bird → Configuration → Message Templates, synced from Bird).
- **Click-to-call error about the agent phone** — set *Bird Agent Phone*
  on the Connect user.
- Enable *Debug Mode* in core Connect settings to log every Bird API
  request/response into the Debug Log.
