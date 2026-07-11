# Bird Integration

The `connect_bird` module connects Odoo to [Bird.com](https://bird.com)
(formerly MessageBird): SMS and WhatsApp messaging (including approved
WhatsApp templates), a call ledger fed by Bird voice events, click-to-call
and call recordings.

## How it works

Odoo talks to the Bird REST API (`api.bird.com`) with a workspace access
key. Bird pushes messaging and voice events back to Odoo through **one
webhook endpoint** (`/bird/webhook`), signed with a per-subscription
signing key that Odoo generates for you.

Click-to-call is a **two-leg callback**: Bird first dials the agent's own
phone number, and once the agent answers, bridges the call to the
destination. Bird provides no browser SDK, so there is no web phone — an
agent needs a real phone number (mobile or landline).

Inbound call *routing* (IVRs, queues) stays in Bird's own Flow Builder;
Odoo records the resulting calls in the shared Connect ledger.

## 1. Install the module

Install `connect_bird` like any Odoo addon.

## 2. Create a Bird access key

In your Bird workspace open **Settings → Access keys** and create a key
with permissions for Channels (messages), Voice (calls, recordings) and
Notifications (webhook subscriptions). Note your **workspace ID** (visible
in the workspace URL or settings).

## 3. Configure Connect → Bird → Configuration → Settings

| Setting | Meaning |
|---------|---------|
| Bird Workspace ID | The workspace uuid |
| Access Key | The access key from step 2 (stored masked) |
| Agent Ring Timeout | How long Bird rings the agent phone on click-to-call |

Click **SYNC BIRD ACCOUNT** — this imports your Bird **channels** (SMS,
WhatsApp and Voice numbers) into *Connect → Bird → Channels* and your
approved **WhatsApp message templates**.

Mark one channel per platform as *Default* if you have several.

## 4. Set up webhooks

Click **SETUP WEBHOOKS**. Odoo generates a signing key and registers six
workspace subscriptions (`sms`/`whatsapp`/`voice` × `inbound`/`outbound`)
pointing to `<your Odoo URL>/bird/webhook`. The registered subscriptions
are listed under *Bird → Configuration → Webhook Subscriptions*.

Requirements:

- The Odoo **API URL** (Connect → Configuration → Settings) must be a
  public HTTPS URL reachable by Bird.
- Signature verification is on by default; the timestamp tolerance and a
  development-only bypass live on the *Development* tab of the Bird
  settings (visible with developer mode).

## 5. Configure users

On each Connect user (Connect → Users):

| Field | Meaning |
|-------|---------|
| Bird Agent Phone | E.164 number Bird dials first on click-to-call |
| Bird Voice Channel | Voice channel used to originate (default channel when empty) |
| Bird Message Channel | Default sender for outgoing messages |
| Click-to-call Provider | Set to *Bird* when several telephony modules are installed |
| Messaging Provider | Set to *Bird* when several messaging modules are installed |

## 6. Message routing (optional)

*Bird → Configuration → Message Configuration* maps a Bird channel to a
destination model for inbound messages from unknown senders (default:
create a partner). `default_values` is a Python dict literal merged into
the created record.

## Recordings

When *Record Calls* is enabled on the Connect user, click-to-call calls
are recorded by Bird. A scheduled action ("Connect Bird: Fetch Call
Recordings", every 2 minutes) downloads finished recordings into the
Connect ledger — Bird's download links expire after 10 minutes, so the
audio is stored as an Odoo attachment. Transcription then works exactly
like for any other provider (OpenAI key in core Connect settings).

## Troubleshooting

- **401 in Bird webhook logs** — signing key mismatch: re-run **SETUP
  WEBHOOKS** and delete stale subscriptions in the Bird dashboard.
  Webhook delivery logs are available in Bird for seven days.
- **WhatsApp message fails immediately** — the 24-hour customer-service
  window is closed: start the conversation with an approved template
  (Bird → Configuration → Message Templates, synced from Bird).
- **Click-to-call error about the agent phone** — set *Bird Agent Phone*
  on the Connect user.
- Enable *Debug Mode* in core Connect settings to log every Bird API
  request/response into the Debug Log.
