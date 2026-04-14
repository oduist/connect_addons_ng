# Oduist Connect

Modular telephony integration platform for Odoo. Make and receive calls, send SMS and WhatsApp messages, record and transcribe conversations — all from within Odoo.

## Architecture

Connect consists of three modules:

| Module | Purpose |
|--------|---------|
| **connect** | Technology-agnostic core. Stores calls, messages, recordings, users, callflows, extensions. Handles AI transcription and summarization. |
| **connect_twilio** | Twilio integration. Adds Twilio Voice SDK phone widget, SIP domains, WhatsApp, TwiML apps. |
| **connect_freeswitch** | FreeSWITCH integration. Adds Verto WebRTC client, XML dialplan generation, SIP gateways. |

Install the **connect** core module plus one integration module matching your telephony provider.

## Key Features

- **Calls** — Incoming, outgoing, and internal calls with full history and partner linking
- **Phone Widget** — Browser-based phone (Twilio Voice SDK or FreeSWITCH Verto WebRTC)
- **IVR / Call Flows** — Multi-level interactive voice response with DTMF and speech input
- **Call Recording** — Automatic or per-user recording with in-browser playback
- **AI Transcription** — OpenAI Whisper speech-to-text and GPT-4o call summaries
- **SMS & WhatsApp** — Send and receive messages with delivery tracking
- **Partner Integration** — Automatic caller ID lookup and call/message history on contacts

## Quick Start

1. Install the core module (`connect`) and your integration module
2. Configure the telephony provider in **Connect > Configuration > Settings**
3. Create PBX users in **Connect > PBX > Users**
4. Set up phone numbers in **Connect > PBX > Numbers**
5. Start making calls from the phone widget in the Odoo navbar

See the [Admin Guide](admin/installation.md) for detailed setup instructions.
