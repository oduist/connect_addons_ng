# Installation

## Requirements

- Odoo 17.0, 18.0, or 19.0
- Python packages: `phonenumbers`, `jinja2`, `openai`
- One telephony provider: Twilio account or FreeSWITCH server

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
    - `connect_twilio` or `connect_freeswitch` (choose one)

2. Install Python dependencies:

    ```bash
    pip install phonenumbers jinja2 openai
    # For Twilio:
    pip install twilio
    ```

3. Update the Odoo module list: **Settings > Apps > Update Apps List**

4. Search for "Oduist Connect" in the Apps menu and install it

5. Install the integration module:
    - **Oduist Connect Twilio** for Twilio
    - **Oduist Connect FreeSWITCH** for FreeSWITCH

## Post-Installation

After installation, navigate to **Connect > Configuration > Settings** to configure your telephony provider. See the provider-specific setup guides:

- [Core Configuration](core-setup.md) — General settings, transcription, registration
- [Twilio Setup](twilio-setup.md) — Twilio account, SIP domains, WhatsApp
- [FreeSWITCH Setup](freeswitch-setup.md) — FreeSWITCH server, gateways, endpoints
