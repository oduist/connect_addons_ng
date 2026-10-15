# Installation

## 1. Install the Python dependency

The module declares `elevenlabs` as an external Python dependency. Install it in
the same environment that runs Odoo:

```bash
pip install elevenlabs
```

The integration was validated against the ElevenLabs SDK `2.58.0`. If the
package is missing, Odoo will refuse to install `connect_elevenlabs` and report
the unmet dependency.

## 2. Install the module

`connect_elevenlabs` depends on the core `connect` module, the Twilio module
`connect_twilio`, and the Odoo `calendar` application:

```
connect_elevenlabs
  depends: ['connect', 'connect_twilio', 'calendar']
  python:  ['elevenlabs']
```

Install it from **Apps** (search for *Connect ElevenLabs*) or from the command
line:

```bash
odoo -d <database> -i connect_elevenlabs
```

!!! warning "Install and configure Twilio first"
    ElevenLabs is a Twilio add-on. Inbound calls always arrive through Twilio and
    are handed off to ElevenLabs' SIP ingress. Make sure `connect_twilio` is
    installed, credentials are set, the core **API URL** points at your public
    HTTPS Odoo URL, and at least one Twilio number is working **before** you rely
    on ElevenLabs routing.

## 3. Install and pre-install hooks

The module runs a `pre_init_hook` and a `post_init_hook`:

- **`pre_init_hook`** (`relink_orphan_agent_tools`) heals orphaned seed tools
  before the data files load. A seed agent-tool row can outlive its
  `ir.model.data` XML-ID link (uninstall leftovers, a partial database restore,
  manual cleanup); without the link the data loader would try to `INSERT` the
  seed tool again and fail on the `UNIQUE(name)` constraint. The hook re-creates
  the missing links so the loader falls back to `UPDATE`. It is safe to run
  repeatedly and on a fresh install.
- **`post_init_hook`** stamps the module install date and refreshes the Oduist
  license status (`oduist.license.update_license_status`). ElevenLabs registers
  itself as a licensed Oduist module.

## 4. What the install adds

- The **Connect ▸ ElevenLabs** submenu: **Agents**, **Agent Templates** (admin),
  **Voices**, **Tools**, and **Configuration ▸ Settings** (admin).
- The ElevenLabs models under `connect.elevenlabs_*` (agent, agent prompt,
  agent template, agent transfer, voice, file) plus `connect.agent_tool_params`.
- ElevenLabs fields added to shared and Twilio models: `connect.settings`
  (credentials, webhook wiring), `connect.call` (agent, summary, transcript,
  conversation id), `connect.recording` (transcript/summary/media), and the
  retargeted Twilio models — `connect.twilio.number` (`elevenlabs_agent`
  destination), `connect.twilio.exten` (agent `dst`, re-added `is_published`
  flag), `connect.twilio.callflow` (ElevenLabs TTS prompts), and `connect.user`
  (ElevenLabs voicemail prompt).
- A library of seed **agent tools** (`data/tools.xml`): system tools, the
  transfer / create-partner webhook tools, and five calendar tools.
- A sample **agent template** (`data/agent_templates.xml`) — *Appointment
  Assistant*.

!!! note "No scheduled jobs"
    Unlike the Twilio module, `connect_elevenlabs` ships **no cron jobs**. All
    ElevenLabs work happens synchronously on record save (agent/tool sync) or on
    inbound webhooks (per-call and post-call). Transcription reuses the core
    recording pipeline.

## 5. Co-installation with other providers

ElevenLabs is specifically a Twilio add-on and cannot be used with another
provider's numbering plan — it retargets the `connect.twilio.*` models. It can
still be co-installed in a database that also runs FreeSWITCH, Telnyx, Asterisk,
etc., but agents will only answer calls that arrive through Twilio numbers,
extensions or WhatsApp senders.

## Version note

Python source is identical across the 17.0 / 18.0 / 19.0 series branches; only
XML views and per-series migrations differ. Version-specific behaviour (for
example the `Constraint` class on Odoo 19, or `Html` fields from 17.0 onward) is
handled by branching on `release.version_info[0]` inside the shared file. The
manifest version tail (for example `1.0.0`) is the product version and is
aligned across branches; the leading `19.0.` only marks the target Odoo series.
