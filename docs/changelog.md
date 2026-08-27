---
title: Changelog
hide:
  - navigation
---

# Changelog

All notable changes to Oduist Connect are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

!!! note "Why entries are dated rather than numbered"
    Every module carries its own version and they move independently — core
    `connect` is well ahead of the providers, and each provider ahead of the
    ones added after it. No single number describes a release of "Connect" as a
    whole, so entries are grouped by the month they shipped in. The version a
    given module is at is shown on its card in **Apps**.

Entries were reconstructed from the commit history of the `19.0` branch, read
from the changes themselves rather than from commit subjects. Work nobody
outside the repository would notice — refactoring, formatting, tests, CI,
version bumps, repository moves — is deliberately left out.

## [Unreleased]

### Added
- **connect_book** — New module: read this documentation inside Odoo, under
  **Connect ▸ Documentation**. It serves the pages of the Connect modules you
  actually have installed, split into a
  [User Guide](Book/user/reading-the-docs.md) for everyone with a Connect role
  and an Admin Guide for Connect administrators.

### Changed
- Every module's Apps Store page was rebuilt in the Aurora house style, and the
  Accounting, HR, Project and Sales bridges got one for the first time.

---

## 2026-08

### Added
- **connect_telnyx** — AI receptionist routing, with voice controls for the
  assistant.
- **connect_freeswitch** — The browser softphone speaks German, French, Italian
  and Russian. It follows your Odoo interface language and falls back to
  English.
- **connect_freeswitch** — Fallback routing for call queues, so a queue nobody
  answers hands the call on instead of dropping it.

### Changed
- The documentation moved into each module's own folder, and the site was
  rebuilt on an in-house theme.

### Fixed
- **connect_telnyx** — Inbound number routing, click-to-call and the WhatsApp
  transport were all broken and have been repaired.
- **connect_telnyx** — Account synchronisation, SIP domain and extension
  creation are hardened against partial or failed setup.
- **connect_telnyx** — An account not authorised for Voice/TeXML now reports a
  clear error instead of a bare HTTP 403.
- **connect_telnyx** — TeXML and call-recording fixes.
- **connect_freeswitch** — Queues reload automatically when you change one, so
  edits take effect without restarting the server.
- **connect_freeswitch** — The external SIP profile is served even when no
  gateway is configured yet, so a fresh install no longer looks broken.

---

## 2026-07

The month the platform became multi-provider: eleven new integrations, and the
model separation that lets them run side by side.

### Added
- **connect_asterisk** — Connect an existing Asterisk, FreePBX or Issabel PBX
  through a lightweight sidecar agent: live call events, click-to-call, a
  browser SIP phone, and generated configuration snippets.
- **connect_telnyx** — Telnyx integration: TeXML call flows, SIP domains,
  per-user telephony credentials, a WebRTC phone, SMS, WhatsApp and RCS. Later
  in the month it gained AI voice assistants.
- **connect_infobip** — Infobip integration: event-driven cloud voice, a WebRTC
  phone, SMS and WhatsApp.
- **connect_bird** — Bird.com (ex-MessageBird) messaging: SMS and WhatsApp with
  approved templates, call logging, and click-to-call by two-leg callback.
- **connect_vonage** — Vonage integration: NCCO call flows, browser calling, IVR
  and SMS.
- **connect_3cx** — Connect an existing 3CX V20 PBX: contact lookup when a call
  arrives, call journaling when it ends, and click-to-call through the 3CX Web
  Client.
- **connect_livekit** — Self-hosted realtime stack: video rooms with public
  guest links and recording, SIP telephony over your own carrier trunk, and
  voice-AI agents.
- **connect_elevenlabs** — ElevenLabs conversational-AI voice agents as a Twilio
  add-on, with agent prompts, templates, tools and warm transfers, plus
  sub-modules for Helpdesk, Knowledge and Sales.
- **connect_dograh** — Dograh AI voice agents answering and placing calls on
  your FreeSWITCH lines.
- **connect_pipecat** — Pipecat open-source AI voice agents on FreeSWITCH.
- **connect_freeswitch_website** — Phone Status and Phone Opening Hours website
  snippets, driven by your numbers' working schedules.
- Working schedules for inbound calls: a number can be open, closed, or on a
  special-day exception, and routes accordingly.
- Recording controls in the browser softphone for Twilio and FreeSWITCH — pause
  and resume a recording during the call.
- Per-user language and voice for text-to-speech prompts.
- **connect_freeswitch** — The SIP firewall handles IPv6.
- The documentation site, published from the repository.
- An Apps Store page for every module.

### Changed
- **Provider model separation.** Extensions, numbers, call flows, caller IDs and
  endpoints are now owned by each provider instead of shared, so a FreeSWITCH
  extension and a Twilio extension are independent records. Several providers
  can be installed in one database, with each user choosing which one places
  their calls and which one sends their messages.
- All Connect modules moved to the Business Source License 1.1.
- The active-calls and Calls widgets moved into core, so every provider shows
  the same thing.

### Fixed
- **connect_twilio** — Speech call flows lost their recognition hints.
- **connect_twilio** — Call-flow voicemail behaved incorrectly.
- **connect_freeswitch** — A user's voicemail fallback did not trigger.
- **connect_freeswitch** — The firewall service shuts down gracefully instead of
  dropping its state.
- A dead "default" checkbox was removed from the Numbers form.

### Security
- FreeSWITCH → Odoo endpoints are authenticated, and the webhook grant was
  removed from the Twilio auth token, so one provider's credential no longer
  carries another's privileges.
- FreeSWITCH's XML-RPC interface is served over HTTPS behind Traefik with an
  administrator-only password, and FreeSWITCH connectivity as a whole moved
  behind the TLS edge.

---

## 2026-06

### Added
- **connect_crm** — Calls link to leads and opportunities, leads can be
  auto-created from calls, calls are attributed to UTM sources by phone number,
  and AI call summaries are posted to the lead's chatter.
- **connect_helpdesk** — Calls are matched to helpdesk tickets by number, with a
  Calls smart button on the ticket and a live call popup for agents.
- **connect_freeswitch** — Endpoint authentication passwords are generated as
  passphrases instead of being set by hand.

### Changed
- Caller IDs are normalised to E.164 before a contact is matched, so the same
  number written three ways still finds one contact.
- **connect_freeswitch** — The WebRTC/Verto password is rotated every time
  credentials are issued.

### Fixed
- **connect_freeswitch** — Inbound number matching tolerates an optional leading
  `+`.
- **connect_freeswitch** — A system-wide default number is used as the outbound
  caller ID when nothing more specific applies.
- **connect_freeswitch** — Server Status distinguishes its failure modes instead
  of reporting one generic error.
- **connect_freeswitch** — Call direction in the call record follows the
  direction Odoo registered.
- **connect_freeswitch** — The external SIP profile starts when the first
  gateway is created.

### Security
- **connect_freeswitch** — The caller's name is no longer disclosed on outbound
  PSTN legs.

---

## 2026-05

### Added
- **connect_freeswitch** — SIP firewall: an Odoo-managed brute-force protection
  service for the SIP port, with a readiness check of its own.
- **connect_freeswitch** — Call flows carry a language selection, backed by an
  extended Piper voice bundle.
- **connect_freeswitch** — Music on hold ships out of the box.

### Fixed
- **connect_freeswitch** — A misconfigured gateway is reported as "Not loaded"
  rather than "Parse error".
- **connect_freeswitch** — IVR DTMF menus, and leftover state after a queue is
  removed.
- **connect_freeswitch** — The outgoing caller ID is honoured on external
  outbound calls, including calls started from a SIP phone.
- **connect_freeswitch** — The freshest non-expired certificate is picked from
  Traefik's store, so renewal no longer needs a manual restart.
- **connect** — The outgoing caller-ID selection no longer carries a
  Twilio-only condition, so it behaves for every provider.

---

## 2026-04

### Added
- **connect_freeswitch** — Call parking, with busy-lamp indication, a softphone
  tab and a Park button.
- **connect_freeswitch** — Call queues, with music on hold, ring-all members and
  a timeout fallback.
- **connect_freeswitch** — Call recording, Piper text-to-speech voices, gateway
  access lists, click-to-call, auto-answer over WebRTC, and generated dialplans.
- A migration path from the old monolithic `connect` to the split
  `connect` + `connect_twilio`.

### Fixed
- **connect_freeswitch** — SIP phones behind NAT are handled correctly.

---

## 2026-03

### Added
- **connect_twilio** — The Twilio integration became a module of its own.
- **connect_freeswitch** — Call detail records are read from FreeSWITCH.

### Changed
- **The platform was split into a technology-agnostic core plus provider
  modules.** `connect` keeps the shared call, message and recording history and
  knows nothing about any particular telephony vendor; TwiML and everything else
  Twilio-specific moved into `connect_twilio`. This is the architecture
  everything since has been built on.
- Licensing and registration were carried over to the modular layout.

---

## 2026-02

### Added
- The `19.0` series opens, with the technology-agnostic core and the FreeSWITCH
  integration.

---

## How to add an entry

Add a bullet under **Unreleased** in the same pull request that makes the
change, then move the block under a new dated heading when it ships.

- Write for the reader of the docs, not the reviewer of the diff: say what
  changed for an administrator or user, not which function was refactored.
- Name the module in bold when a change is provider-specific, e.g.
  **connect_telnyx**.
- Link to the page that documents the change where one exists.
- Leave out what nobody outside the repository would notice: refactoring,
  formatting, tests, CI, version bumps.

```markdown
## 2026-09

### Added
- **connect_telnyx** — Call-failure notifications in the web phone, including a
  balance-blocked warning for administrators.
```
