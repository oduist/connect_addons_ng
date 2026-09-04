# Installation

## Requirements

- Odoo 17.0, 18.0, or 19.0
- Python packages: `phonenumbers`, `jinja2`, `httpx`, `openai`, `PyJWT`
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
    pip install phonenumbers jinja2 httpx openai PyJWT
    # For Twilio:
    pip install twilio
    ```

3. Update the Odoo module list: **Settings > Apps > Update Apps List**

4. Search for "Oduist Connect" in the Apps menu and install it

5. Install the integration module(s):
    - **Oduist Connect Twilio** for Twilio
    - **Oduist Connect FreeSWITCH** for FreeSWITCH
    - **Oduist Connect Asterisk** for an existing Asterisk PBX

6. Optionally install the business-record bridges, which attach calls to the
   Odoo records they belong to (see
   [Calls and Business Records](../user/business-records.md)):
    - **Oduist Connect CRM** — leads and opportunities
    - **Oduist Connect Helpdesk** — tickets
    - **Oduist Connect HR** — employees
    - **Oduist Connect Sale** — sale orders
    - **Oduist Connect Account** — customer invoices
    - **Oduist Connect Project** — tasks and projects

    Each bridge depends only on `connect` plus its own Odoo app, so they are
    independent of the telephony provider you chose above and can be combined
    freely.

## Post-Installation

Each installed integration adds its own submenu (**Twilio**, **FreeSWITCH**,
**Asterisk**) inside the **Connect** app with a **Configuration > Settings**
entry for the provider credentials; core options live in **Connect >
Configuration > Settings**. See the provider-specific setup guides:

- [Core Configuration](core-setup.md) — General settings, transcription
- [Twilio Setup](../../Twilio/index.md) — Twilio account, SIP domains, WhatsApp
- [FreeSWITCH Setup](../../FreeSWITCH/admin/freeswitch-setup.md) — FreeSWITCH server, gateways, endpoints
- [Asterisk Setup](../../Asterisk/admin/asterisk-setup.md) — Sidecar agent, endpoints, config snippets
