# Vonage Integration

The `connect_vonage` module connects Odoo to the Vonage (ex-Nexmo)
platform: inbound/outbound calls with NCCO call control, a browser web
phone based on the Vonage Client SDK, SMS through the Messages API and
call recordings with AI transcription.

## Prerequisites

- An Odoo instance reachable over **public HTTPS** (Vonage webhooks and
  the signed-callback JWTs require it). Verify `connect.api_url` in
  System Parameters before syncing.
- A Vonage API account with an API key and secret
  ([dashboard.vonage.com](https://dashboard.vonage.com/)).
- The `vonage` Python package installed in the Odoo environment
  (`pip install vonage`).

## Configuration

1. Install the `connect_vonage` module (requires `connect`).
2. Open **Connect → Settings → Vonage API** and fill in:
   - **API Key** and **API Secret** — from the Vonage Dashboard →
     **Settings** (API keys section; expand your username in the left
     sidebar → Settings). The API secret is shown only at creation.
   - **Signature Secret** — from the same Dashboard → **Settings** page
     (*Signature secret*). It authenticates incoming webhooks (signed
     callbacks).
   - **Region** — optional voice region for the application.
3. Click **SYNC VONAGE ACCOUNT**. The sync:
   - creates a Vonage **Application** with voice, messages (v1) and RTC
     capabilities, `signed_callbacks` enabled and all webhook URLs
     pointing to your Odoo instance, and stores the application ID and
     its private key;
   - creates a Vonage **User** for every Connect user with a username;
   - imports your **numbers** and links them to the application;
   - seeds **outgoing caller IDs** from the imported numbers.

!!! warning "Application private key"
    Vonage returns the application private key **only when the
    application is created**. The sync stores it automatically. If you
    want to reuse an existing application instead, fill in its ID and
    paste its private key manually before syncing.

To re-point webhooks after a domain change, fix `connect.api_url` and
run the sync again.

## Users and the web phone

Each Connect user needs an alphanumeric **Username**. The web phone
(systray icon) logs into the Vonage Client SDK with a JWT minted by
Odoo; enable/disable it per user with **Web Phone Enabled** on the
user's Phone tab. Calls to the user ring the browser via the
application (`app`) endpoint.

## Numbers and routing

Imported numbers appear under **Connect → Numbers**. Set each number's
**Destination**: a user, a call flow (IVR) or an **NCCO** application
(Connect → Vonage → NCCO — static JSON, jinja2-templated JSON, Python
or `model.method`).

## Recordings and voicemail

Vonage recording files require JWT authentication, so recordings are
downloaded by Odoo (a 2-minute cron retries failures) and stored as
attachments; transcription runs after the download. Voicemail messages
are stored as recordings with source `voicemail`.

## Known limitations

- Ring groups ring users **sequentially** (Vonage NCCO `connect` takes
  a single endpoint).
- WhatsApp/MMS sending, call transfer and simultaneous ring are not
  available yet (see ADR-036).
