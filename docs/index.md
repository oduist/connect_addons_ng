# Oduist Connect

Modular telephony integration platform for Odoo. Make and receive calls, send SMS and WhatsApp messages, record and transcribe conversations — all from within Odoo.

## Architecture

Connect consists of a core module plus provider integrations:

| Module | Purpose |
|--------|---------|
| **connect** | Technology-agnostic core. Stores calls, messages, recordings and users. Handles AI transcription and summarization. |
| **connect_twilio** | Twilio integration. Owns its numbers, extensions, call flows and caller IDs; adds Twilio Voice SDK phone widget, SIP domains, WhatsApp, TwiML apps. |
| **connect_freeswitch** | FreeSWITCH integration. Owns its numbers, extensions, call flows, endpoints and caller IDs; adds Verto WebRTC client, XML dialplan generation, SIP gateways. |
| **connect_asterisk** | Asterisk integration for existing PBXs. Owns its endpoints and DID mappings; adds JsSIP web phone and AMI event pipeline via a sidecar agent. |
| **connect_telnyx** | Telnyx integration. Owns its numbers, extensions, call flows and caller IDs; adds Telnyx WebRTC phone widget, SIP domains (credential connections), TeXML apps, SMS. |

Install the **connect** core module plus the integration module(s) matching your telephony provider — several providers can coexist in one database. Each integration adds its own submenu (**Twilio**, **FreeSWITCH**, **Asterisk**, **Telnyx**) inside the **Connect** app, after **Calls** and in installation order.

## Key Features

- **Calls** — Incoming, outgoing, and internal calls with full history and partner linking
- **Phone Widget** — Browser-based phone (Twilio Voice SDK, FreeSWITCH Verto WebRTC, Asterisk JsSIP, or Telnyx WebRTC)
- **IVR / Call Flows** — Multi-level interactive voice response with DTMF and speech input
- **Call Recording** — Automatic or per-user recording with in-browser playback
- **AI Transcription** — OpenAI Whisper speech-to-text and GPT-4o call summaries
- **SMS & WhatsApp** — Send and receive messages with delivery tracking
- **Partner Integration** — Automatic caller ID lookup and call/message history on contacts

## Quick Start

1. Install the core module (`connect`) and your integration module
2. Configure the telephony provider in its own menu, e.g. **Connect > Twilio > Configuration > Settings** or **Connect > FreeSWITCH > Configuration > Settings**
3. Create PBX users in **Connect > Users**
4. Set up phone numbers in the provider menu, e.g. **Connect > Twilio > Numbers** or **Connect > FreeSWITCH > Numbers**
5. Start making calls from the phone widget in the Odoo navbar

See the [Admin Guide](admin/installation.md) for detailed setup instructions.
