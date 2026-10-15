# Installation

## 1. Install the Python dependency

The module declares `twilio` as an external Python dependency. Install it in the
same environment that runs Odoo:

```bash
pip install twilio
```

If the package is missing, Odoo will refuse to install `connect_twilio` and
report the unmet dependency.

## 2. Install the module

`connect_twilio` depends only on the core `connect` module:

```
connect_twilio
  depends: ['connect']
  python:  ['twilio']
```

Install it from **Apps** (search for *Oduist Connect Twilio*) or with the
command line:

```bash
odoo -d <database> -i connect_twilio
```

On install a `post_init_hook` runs, which stamps the module install date and
refreshes the Oduist license status. Twilio is a **licensed** Oduist module —
outbound origination checks the `connect` license before placing a call, so make
sure your license is valid (see [Maintenance ▸ Licensing](maintenance.md#licensing)).

## 3. What the install adds

- The **Connect ▸ Twilio** submenu (Numbers, Extensions, Call Flows, Outgoing
  Caller IDs, TwiML Apps, SIP Domains, Messages, Configuration).
- The Twilio-specific fields on the shared Connect models (users, calls,
  channels, messages, recordings, settings).
- The Twilio Voice SDK web-phone assets in the Odoo backend.
- A scheduled job **Fetch Call Prices from Twilio** (disabled effect until you
  enable *Fetch Call Prices* in settings — see
  [Maintenance ▸ Scheduled jobs](maintenance.md#scheduled-jobs)).
- The `voice_call_request` default WhatsApp content template.

## 4. Co-installation with other providers

Twilio can run side-by-side with the other Connect providers (FreeSWITCH,
Telnyx, Asterisk, etc.) in one database. In a multi-provider database:

- Per-user **click-to-call provider** (`originate_provider`) selects which module
  places outbound calls.
- Per-user **message provider** (`message_provider`) selects which module sends
  SMS/WhatsApp.
- The Twilio **web phone** is enabled by default *only* when Twilio is the sole
  installed telephony module. With several providers installed you enable it
  explicitly per user (see [Users, SIP & Web Phone](users-and-sip.md)).

## Version note

Python source is identical across the 17.0 / 18.0 / 19.0 series branches; only
XML views and per-series migrations differ. The manifest version tail (for
example `2.2.0`) is the product version and is aligned across branches; the
leading `19.0.` only marks the target Odoo series.
