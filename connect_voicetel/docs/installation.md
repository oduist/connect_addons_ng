# Installation

## 1. Python dependency

The module uses VoiceTel's own VoiceML SDK as its REST client and webhook
validator, and builds VoiceML markup with its own builder:

```bash
pip install voiceml
```

The SDK is pointed at the VoiceML host by the module; nothing contacts
Twilio.

## 2. Install the module

Install **Oduist Connect VoiceTel** (`connect_voicetel`) from Apps. It
depends on the core `connect` module only.

On installation the module:

- adds the `voicetel` provider key to the per-user **Click-to-call provider**
  and **Messaging provider** selections;
- creates the required **SIP Domain Calls** VoiceML app (the application
  every tenant SIP domain points at) and two example apps (Reject,
  Connection Failed);
- registers the **Fetch Call Prices from VoiceML** scheduled action
  (inactive until price fetching is enabled in the settings).

## 3. Public HTTPS URL

VoiceML reaches Odoo through webhooks. Set **Connect ▸ Configuration ▸
Settings ▸ API URL** to the public HTTPS address of this Odoo instance
before synchronizing the account: every voice URL, status callback and
message webhook is built from it.

## 4. Next step

Continue with [Account Configuration](configuration.md).
