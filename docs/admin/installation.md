# Installation

## Requirements

- Odoo 17.0, 18.0, or 19.0
- Python packages: `phonenumbers`, `jinja2`, `openai`
- A telephony provider: Twilio account, FreeSWITCH server, or an existing Asterisk PBX (several providers can be installed side by side)

### Provider-specific requirements

=== "Twilio"

    - Python package: `twilio`
    - Twilio account with Account SID, Auth Token, and API Key/Secret
    - At least one Twilio phone number

=== "FreeSWITCH"

    - FreeSWITCH server (Docker deployment provided)
    - SIP trunk provider (for PSTN calls)
    - Open ports: WSS (48082/tcp), RTP media (16000-17000/udp)

## Installing the Modules

1. Place the module directories in your Odoo addons path:
    - `connect` (required)
    - `connect_twilio`, `connect_freeswitch` and/or `connect_asterisk`

2. Install Python dependencies:

    ```bash
    pip install phonenumbers jinja2 openai
    # For Twilio:
    pip install twilio
    ```

3. Update the Odoo module list: **Settings > Apps > Update Apps List**

4. Search for "Oduist Connect" in the Apps menu and install it

5. Install the integration module(s):
    - **Oduist Connect Twilio** for Twilio
    - **Oduist Connect FreeSWITCH** for FreeSWITCH
    - **Oduist Connect Asterisk** for an existing Asterisk PBX

## Post-Installation

Each installed integration adds its own top-level menu (**Twilio**,
**FreeSWITCH**, **Asterisk**) with a **Configuration > Settings** entry for the
provider credentials; core options live in **Connect > Configuration >
Settings**. See the provider-specific setup guides:

- [Core Configuration](core-setup.md) — General settings, transcription
- [Twilio Setup](twilio-setup.md) — Twilio account, SIP domains, WhatsApp
- [FreeSWITCH Setup](freeswitch-setup.md) — FreeSWITCH server, gateways, endpoints
- [Asterisk Setup](asterisk-setup.md) — Sidecar agent, endpoints, config snippets
