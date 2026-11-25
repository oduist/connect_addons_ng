# Account Configuration

## Getting a VoiceML account

A VoiceML account is provisioned by VoiceTel on top of a verified VoiceTel
customer account. Complete these steps before configuring the module:

1. **Sign up** at <https://voicetel.com/signup/> and create your VoiceTel
   customer account.
2. **Complete KYC** (know-your-customer verification) in the VoiceTel
   customer portal. VoiceTel reviews the business details and identity
   documents you submit; phone numbers and outbound calling are only
   enabled once the verification is approved.
3. **Request a VoiceML account** by email to
   [support@voicetel.com](mailto:support@voicetel.com) from the address you
   signed up with. State that the account is for the Odoo Connect VoiceTel
   module. VoiceTel answers with the VoiceML **Account SID** (`AC…`) and the
   **API key**.

!!! warning "The API key is shown once"
    VoiceTel issues the API key a single time. Store it in the module
    settings immediately; a lost key has to be rotated by VoiceTel support.

Open **Connect ▸ VoiceTel ▸ Configuration ▸ Settings**. The form edits the
VoiceTel fields of the shared Connect settings record.

## VoiceML account

| Field | Description |
|-------|-------------|
| **Account SID** | The `AC…` identifier of the VoiceML account. |
| **API Key** | The per-account API key issued by VoiceTel. It is the HTTP Basic password for the REST API **and** the key VoiceML signs its webhooks with. Stored masked; shown once at issue time on the VoiceTel side. |
| **API Host** | Hostname of the VoiceML REST API, `voiceml.voicetel.com` by default. Change it only for a dedicated or self-hosted VoiceML deployment. |

Press **SYNC VOICETEL ACCOUNT** after saving. The sync:

1. mirrors every VoiceML app as an Application on the account;
2. creates the SIP domains defined in Odoo on the account (credential list
   and registration/call mappings included) and updates existing ones;
3. imports the account's phone numbers and points their voice and SMS
   webhooks at Odoo;
4. imports owned numbers and verified caller IDs as outgoing caller IDs.

Records that exist only on the VoiceML account (domains, applications) are
never imported; numbers removed from the account are removed in Odoo.

!!! warning "Set the API URL first"
    The sync writes webhook URLs built from the Connect **API URL**. A sync
    run with a wrong URL has to be repeated after the URL is corrected.

## Balance

**GET VOICETEL BALANCE** reads the account balance through the
Twilio-compatible Balance resource and stores it in **Current Balance**.

## SIP & browser phone

| Field | Description |
|-------|-------------|
| **SIP Domain Suffix** | Tenant SIP domains are created as `<label>.<suffix>`; `vml.voice.tel` by default. The VoiceML registrar authenticates registrations and calls under this suffix only. The SIP over WebSocket address is tied to the domain: `wss://<label>.<suffix>:8443`. |
| **STUN Server** | Optional STUN server handed to the browser phone. |
| **Browser Phone** | Global switch for the browser phone. Each user additionally has their own switch. |

## Calls

**Fetch Call Prices** marks finished calls for the price cron, which reads
the `price` VoiceML computes from the tenant's rates once a call finalizes.

## Development

**Verify VoiceTel Requests** (default on) validates the `X-Twilio-Signature`
header on every webhook with the API key. Turn it off only while debugging
on a non-public URL. The **Auto Sync** toggle (debug mode) stops Odoo from
pushing changes to VoiceML on save.
