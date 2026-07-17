# Oduist Connect — AI Voice Platform for Odoo

**Supported platforms:** Asterisk · FreeSWITCH · Twilio · Telnyx · Bird ·
Infobip · LiveKit · Pipecat · Dograh

**Give Odoo a voice.** Oduist Connect brings AI voice agents that live inside
Odoo — they answer and place real phone calls, qualify leads and help your team
sell, and turn every conversation into structured data on your contacts, leads
and tickets. Behind the agents runs a complete, provider-agnostic communications
stack (voice, SMS / WhatsApp / RCS, video), so the same platform also powers
your human team's web phone, messaging and call recording.

Every call — whether an AI agent or a person is on the line — is recorded,
transcribed and summarized by OpenAI and filed against the right partner, lead
or ticket. Nothing said on the phone is lost to your CRM: the agents sell and
book, and the analytics tell you what worked.

The platform is **modular** — a technology-agnostic **core** plus
**provider-specific extensions** you install for your telephony/messaging
vendor. Providers can run **side by side in one database**: each user picks
which module handles their click-to-call (`originate_provider`) and which
handles their messaging (`message_provider`).

- **Author:** Oduist OÜ
- **Odoo series:** 19.0 (this branch); the same product ships on 18.0 and 17.0
- **License:** Business Source License 1.1 (`BUSL-1.1`) — see [`LICENSE`](LICENSE)
- **Documentation:** <https://oduist.github.io/connect_addons_ng/>

---

## Modules

| Module | Ver. | Purpose |
|--------|:----:|---------|
| **`connect`** | 4.2.0 | Technology-agnostic **core** and Odoo app. Shared call/message ledger (`connect.call`, `connect.channel`, `connect.recording`, `connect.message`), PBX people (`connect.user`), common settings, OpenAI transcription/summarization, working-schedule engine, partner integration. Holds **no** provider-specific code or PBX configuration. |
| **`connect_twilio`** | 2.2.0 | **Twilio** integration. Owns its numbers/extensions/call flows/caller IDs; Twilio Voice JS SDK web phone, SIP domains, TwiML apps, SMS & WhatsApp. |
| **`connect_freeswitch`** | 2.1.1 | **FreeSWITCH** integration (self-hosted). Owns numbers/extensions/call flows/endpoints/caller IDs; Verto WebRTC client, XML dialplan generation, SIP gateways/routes, FIFO, parking, SIP firewall. |
| **`connect_freeswitch_website`** | 1.0.0 | Website snippets for FreeSWITCH number working schedules (Phone Status, Phone Opening Hours) + public `/freeswitch/schedule/*` endpoints. Only module allowed to depend on `website`. |
| **`connect_asterisk`** | 2.1.0 | **Asterisk** integration for existing PBXs (FreePBX / Issabel / plain). Owns endpoints and DID mappings; JsSIP web phone over WSS, click-to-call and AMI event pipeline via the `oduist/asterisk-agent` sidecar, config-snippet generation. |
| **`connect_telnyx`** | 1.3.0 | **Telnyx** integration (TeXML-first). Owns numbers/extensions/call flows/caller IDs; @telnyx/webrtc web phone, SIP domains (credential connections), per-user telephony credentials, SMS / WhatsApp / RCS, Ed25519 webhook validation. |
| **`connect_livekit`** | 1.0.0 | **LiveKit** integration (self-hosted realtime stack). Video rooms with public guest links + Egress recording, SIP telephony via the livekit-sip bridge (BYO trunk), browser web phone, and voice-AI agents served by the `oduist/livekit-agent` sidecar. Admin-only. |
| **`connect_infobip`** | 1.2.0 | **Infobip** integration (event-driven Calls API, no TwiML analog). Webhook events → REST actions, per-user WebRTC identities, vendored infobip-rtc web phone, SMS & WhatsApp, downloaded recordings. No IVR in v1. |
| **`connect_dograh`** | 1.0.0 | **Dograh** AI voice agents on FreeSWITCH. Depends on `connect` **and** `connect_freeswitch`; inbound via per-call dialplan + `mod_audio_fork`, outbound via `/dograh/api/originate`. Ships a vendored Dograh provider overlay (`oduist/dograh-api`). |
| **`connect_pipecat`** | 1.0.0 | **Pipecat** AI voice agents on FreeSWITCH (`mod_audio_fork` + Pipecat sidecar). |
| **`connect_bird`** | 1.0.0 | **Bird.com** (ex-MessageBird) integration. SMS & WhatsApp send/receive on the Bird developer platform (template-first), voice-call ledger, click-to-call via two-leg callback originate (no web phone — Bird has no WebRTC SDK), Standard-Webhooks signatures. |
| **`connect_crm`** | 1.0.0 | Bridges Connect with Odoo **CRM** — call/message history and routing on leads. Depends on `crm`, `utm`. |
| **`connect_crm_twilio`** | 1.0.0 | Auto-installed glue (`connect_crm` + `connect_twilio`): message routing to CRM leads. |
| **`connect_helpdesk`** | 1.0.0 | Bridges Connect with Odoo **Helpdesk** — call/message history on tickets. |

Provider modules (`connect_twilio`, `connect_freeswitch`, `connect_asterisk`,
`connect_telnyx`, `connect_livekit`, `connect_infobip`, `connect_bird`,
`connect_dograh`, `connect_pipecat`) all depend on `connect` and are
**independent of each other**.

---

## Capabilities by provider

| Provider | Voice | Browser web phone | Messaging | IVR / call flows | AI voice agents | Deployment |
|----------|:-----:|:-----------------:|-----------|:----------------:|:---------------:|------------|
| Twilio | ✅ TwiML | ✅ Voice JS SDK | SMS, WhatsApp | ✅ | — | Cloud |
| FreeSWITCH | ✅ XML dialplan | ✅ Verto WebRTC | — | ✅ | via Dograh / Pipecat | Self-hosted |
| Asterisk | ✅ AMI sidecar | ✅ JsSIP | — | (uses existing PBX) | — | Existing PBX |
| Telnyx | ✅ TeXML | ✅ @telnyx/webrtc | SMS, WhatsApp, RCS | ✅ | — | Cloud |
| LiveKit | ✅ SIP bridge | ✅ LiveKit + video | — | — | ✅ built-in | Self-hosted |
| Infobip | ✅ Calls API | ✅ infobip-rtc | SMS, WhatsApp | — | — | Cloud |
| Bird | ✅ ledger | — (callback) | SMS, WhatsApp | — | — | Cloud |

Core features available regardless of provider: unified **call/message ledger**,
**call recording** with in-browser playback, **OpenAI Whisper transcription** and
**GPT-4o summaries**, **working schedules**, and **partner integration** (caller-ID
lookup + call/message history on contacts).

---

## AI voice agents

The heart of the platform. Connect turns your telephony into a place where AI
agents work for you — on real inbound and outbound phone calls, wired straight
into Odoo:

- **`connect_dograh`** — Dograh AI voice agents on FreeSWITCH. Per-call
  dialplan streams audio to the agent (`mod_audio_fork`, L16/16 kHz); inbound
  and outbound both supported.
- **`connect_pipecat`** — Pipecat pipelines on FreeSWITCH (`mod_audio_fork` +
  sidecar), for building custom conversational flows.
- **`connect_livekit`** — LiveKit Agents (STT/LLM/TTS cascade,
  Deepgram / OpenAI / ElevenLabs) served by the `oduist/livekit-agent` sidecar,
  joining rooms alongside SIP callers.

Because every call flows through the shared ledger, agent conversations are
**recorded, transcribed and summarized by OpenAI** and **linked to the matching
partner, lead or ticket** — so an agent can qualify and sell on the phone, and
your team gets the transcript, the summary and the follow-up already sitting on
the CRM record. The communications stack below is the plumbing; the agents and
the data they leave behind in Odoo are the point.

---

## Architecture

Provider model separation (ADR-031): each telephony system lives in its own
numbering plan and business logic. Extensions, numbers, call flows, caller IDs
and endpoints are **independent per-provider models** — a FreeSWITCH extension
has nothing to do with a Twilio extension. Provider modules `_inherit` the
shared ledger models to add adapters that normalize provider events into the
common history.

```
Ledger:  _name = 'connect.call'              → shared, providers _inherit adapters
Config:  _name = 'connect.<provider>.<noun>' → fully owned by the provider module
```

**Boundary rules**

- Core never imports a provider SDK or references provider-specific concepts
  (SIDs, TwiML, TeXML, …).
- OpenAI transcription/summarization lives in core — it is provider-agnostic.
- `connect.message.send()` and `connect.settings.originate_call()` are
  **dispatchers**: each provider override checks its own key
  (`_get_message_provider()` / `_get_originate_provider(user)`) and otherwise
  falls through to `super()`.
- `connect.settings` is a single model; each provider ships its own standalone
  settings form and menu — no notebook pages injected into the core form.

**Security groups:** `connect.group_user` (read), `connect.group_admin` (full
CRUD), `connect.group_webhook` (webhook record creation).

**Webhook routes** are namespaced and authenticated per provider —
`/twilio/webhook/*` (X-Twilio-Signature), `/asterisk/webhook/*` &
`/asterisk/api/*` (Bearer agent token), `/telnyx/webhook/*` (Ed25519),
`/infobip/webhook/*` (shared token), `/livekit/webhook` (JWT WebhookReceiver),
`/dograh/api/*` (Bearer service token), `/bird/webhook` (Standard-Webhooks).

See `specs/architecture.md` for the authoritative design, and
`specs/decisions/` for the Architecture Decision Records (ADRs).

---

## Cross-branch versioning invariant

The **same product ships on each Odoo series** (19.0 / 18.0 / 17.0); only the
leading version prefix differs. A module's `.py` files are **byte-identical
across branches** — a backport touches only XML/HTML views and per-series
`migrations/` entry points, never Python. Where Odoo genuinely behaves
differently between versions, the file branches internally on
`release.version_info[0]` rather than being forked per series.

Manifest versions stay aligned across branches: if a module is `19.0.1.8.13`
here, the same module on 18.0 is `18.0.1.8.13`. The tail (`1.8.13`) is the
product version; the head marks the target Odoo series.

---

## Getting started

1. Install the **`connect`** core module plus the integration module(s) matching
   your provider (e.g. `connect_twilio` or `connect_freeswitch`).
2. Configure the provider in **its own** menu, e.g.
   *Connect → Twilio → Configuration → Settings* or
   *Connect → FreeSWITCH → Configuration → Settings*.
3. Create PBX users in *Connect → Users*.
4. Set up phone numbers in the provider menu.
5. Place and answer calls from the phone widget in the Odoo navbar.

**Python dependencies** (`requirements.txt`): `openai`, `pyjwt`, `twilio`,
`telnyx`, `pynacl`, `livekit-api`. Docker images for the self-hosted stacks
(`oduist/freeswitch`, `oduist/freeswitch-firewall`, `oduist/asterisk-agent`,
`oduist/livekit-agent`, `oduist/dograh-api`) are built from each module's
`deploy/` folder.

Full setup lives in the [Admin Guide](docs/admin/installation.md); end-user
workflows in the [User Guide](docs/user/getting-started.md).

---

## Development

Module development, deployment, and testing run through **oduflow** (per-branch
ephemeral Odoo environments on Docker). Tests are colocated with each module
under `<module>/tests/` and run through Odoo's normal test discovery:

```bash
oduflow run_odoo_tests connect
oduflow run_odoo_tests connect_twilio
oduflow run_odoo_tests connect_freeswitch
# … one target per module
```

Documentation is built with **MkDocs Material** (`mkdocs.yml`). When a code
change adds, removes, or modifies a feature, update the matching files under
`docs/` (user + admin guides) and `specs/` in the **same commit**.

See [`AGENTS.md`](AGENTS.md) for the full contributor guide (conventions,
boundary rules, testing, image versioning, and the ADR workflow).

---

© Oduist OÜ — licensed under the Business Source License 1.1 (`BUSL-1.1`). See
[`LICENSE`](LICENSE) for the full terms.
