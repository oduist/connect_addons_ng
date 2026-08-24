---
title: Oduist Connect
hide:
  - navigation
  - toc
---

<section class="hero-home not-prose">
  <div class="hero-copy">
    <p class="hero-kicker">Oduist Connect</p>
    <h1 class="hero-title">Give Odoo a voice.</h1>
    <p class="hero-lede">
      AI voice agents that live inside Odoo — they answer and place real phone
      calls, qualify leads, and turn every conversation into structured data on
      your contacts, leads and tickets. Behind the agents runs a complete,
      provider-agnostic communications stack — voice, SMS, WhatsApp, RCS and
      video — so the same platform also powers your team's web phone, messaging
      and call recording.
    </p>
    <div class="hero-actions">
      <a class="docs-button docs-button--primary" href="Core/admin/installation/">Installation</a>
      <a class="docs-button" href="changelog/">Changelog</a>
      <a class="docs-button" href="https://github.com/oduist/connect_addons_ng" target="_blank" rel="noopener">View on GitHub</a>
    </div>
  </div>
  <div class="hero-art">
    <img src="assets/img/hero-agent.png" alt="A voice AI agent configured inside Odoo: prompt, conversation, LLM/TTS and knowledge-base tabs." loading="lazy">
  </div>
</section>

<section class="mod-system not-prose">
  <p class="mod-kicker">The module system</p>
  <h2 class="mod-h2">A periodic table of Connect elements.</h2>
  <p class="mod-intro">Every square is one Odoo module from <code>connect_addons_ng</code>. Providers plug in under a technology-agnostic core; agents, apps, and memory sit on top. Click a category to isolate it, or a square to open its documentation.</p>
  <div class="mod-legend" id="mod-legend">
    <button type="button" class="mod-leg" data-cat="core" style="--c:#e66767"><span class="mod-dot"></span>Core</button>
    <button type="button" class="mod-leg" data-cat="provider" style="--c:#3987e5"><span class="mod-dot"></span>Providers</button>
    <button type="button" class="mod-leg" data-cat="agent" style="--c:#9085e9"><span class="mod-dot"></span>AI agents</button>
    <button type="button" class="mod-leg" data-cat="app" style="--c:#199e70"><span class="mod-dot"></span>Odoo apps</button>
    <button type="button" class="mod-leg" data-cat="memory" style="--c:#c98500"><span class="mod-dot"></span>Memory</button>
  </div>
  <div class="mod-grid">
    <a href="Core/admin/installation/" class="mod-tile" data-cat="core" style="--c:#e66767" data-code="connect" data-label="Core" data-tip="One data model for calls, messages, recordings, users and numbers. Providers plug in underneath."><span class="mod-sym">Core</span><span class="mod-nm">Agnostic core</span><span class="mod-code">connect</span></a>
    <a href="Twilio/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_twilio" data-label="Providers" data-tip="Cloud telephony, browser phone, IVR, SMS and WhatsApp."><span class="mod-sym">Tw</span><span class="mod-nm">Twilio</span><span class="mod-code">connect_<wbr>twilio</span></a>
    <a href="Telnyx/admin/telnyx-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_telnyx" data-label="Providers" data-tip="Programmable voice &amp; messaging on TeXML, with native AI Assistants."><span class="mod-sym">Tx</span><span class="mod-nm">Telnyx</span><span class="mod-code">connect_<wbr>telnyx</span></a>
    <a href="FreeSWITCH/admin/freeswitch-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_freeswitch" data-label="Providers" data-tip="Self-hosted PBX: Verto WebRTC, dialplan, FIFO queues, SIP firewall, Piper TTS."><span class="mod-sym">FS</span><span class="mod-nm">FreeSWITCH</span><span class="mod-code">connect_<wbr>freeswitch</span></a>
    <a href="Asterisk/admin/asterisk-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_asterisk" data-label="Providers" data-tip="Connect existing Asterisk, FreePBX or Issabel through an AMI sidecar."><span class="mod-sym">Ast</span><span class="mod-nm">Asterisk</span><span class="mod-code">connect_<wbr>asterisk</span></a>
    <a href="3CX/admin/3cx-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_3cx" data-label="Providers" data-tip="Sync 3CX V20 contacts and the call journal with Odoo."><span class="mod-sym">3CX</span><span class="mod-nm">3CX</span><span class="mod-code">connect_<wbr>3cx</span></a>
    <a href="Infobip/admin/infobip-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_infobip" data-label="Providers" data-tip="Event-driven Calls API, WebRTC, SMS and WhatsApp."><span class="mod-sym">Ib</span><span class="mod-nm">Infobip</span><span class="mod-code">connect_<wbr>infobip</span></a>
    <a href="Bird/admin/bird-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_bird" data-label="Providers" data-tip="SMS and WhatsApp via Bird.com, with callback click-to-call."><span class="mod-sym">Bd</span><span class="mod-nm">Bird</span><span class="mod-code">connect_<wbr>bird</span></a>
    <a href="Vonage/admin/vonage-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_vonage" data-label="Providers" data-tip="NCCO telephony, browser calling, IVR and SMS."><span class="mod-sym">Vo</span><span class="mod-nm">Vonage</span><span class="mod-code">connect_<wbr>vonage</span></a>
    <a href="LiveKit/admin/livekit-setup/" class="mod-tile" data-cat="provider" style="--c:#3987e5" data-code="connect_livekit" data-label="Providers" data-tip="Realtime video, SIP, browser phone and native LiveKit Agents."><span class="mod-sym">LK</span><span class="mod-nm">LiveKit</span><span class="mod-code">connect_<wbr>livekit</span></a>
    <a href="ElevenLabs/" class="mod-tile" data-cat="agent" style="--c:#9085e9" data-code="connect_elevenlabs" data-label="AI agents" data-tip="Conversational voice agents in 27 languages, over your telephony transport."><span class="mod-sym">11</span><span class="mod-nm">ElevenLabs</span><span class="mod-code">connect_<wbr>elevenlabs</span></a>
    <a href="elevenlabs-helpdesk/" class="mod-tile" data-cat="agent" style="--c:#9085e9" data-code="connect_elevenlabs_helpdesk" data-label="AI agents" data-tip="Agents that open and update helpdesk tickets."><span class="mod-sym">11h</span><span class="mod-nm">ElevenLabs · Helpdesk</span><span class="mod-code">connect_<wbr>elevenlabs_<wbr>helpdesk</span></a>
    <a href="elevenlabs-knowledge/" class="mod-tile" data-cat="agent" style="--c:#9085e9" data-code="connect_elevenlabs_knowledge" data-label="AI agents" data-tip="Ground agents in your Odoo knowledge base."><span class="mod-sym">11k</span><span class="mod-nm">ElevenLabs · Knowledge</span><span class="mod-code">connect_<wbr>elevenlabs_<wbr>knowledge</span></a>
    <a href="elevenlabs-sales/" class="mod-tile" data-cat="agent" style="--c:#9085e9" data-code="connect_elevenlabs_sale" data-label="AI agents" data-tip="Agents that find products and place sales orders."><span class="mod-sym">11s</span><span class="mod-nm">ElevenLabs · Sales</span><span class="mod-code">connect_<wbr>elevenlabs_<wbr>sale</span></a>
    <a href="Dograh/admin/dograh-setup/" class="mod-tile" data-cat="agent" style="--c:#9085e9" data-code="connect_dograh" data-label="AI agents" data-tip="External voice agent framework, bridged via FreeSWITCH."><span class="mod-sym">Dg</span><span class="mod-nm">Dograh</span><span class="mod-code">connect_<wbr>dograh</span></a>
    <a href="Pipecat/admin/pipecat-setup/" class="mod-tile" data-cat="agent" style="--c:#9085e9" data-code="connect_pipecat" data-label="AI agents" data-tip="Open-source voice agent pipeline, bridged via FreeSWITCH."><span class="mod-sym">Pc</span><span class="mod-nm">Pipecat</span><span class="mod-code">connect_<wbr>pipecat</span></a>
    <a href="CRM/" class="mod-tile" data-cat="app" style="--c:#199e70" data-code="connect_crm" data-label="Odoo apps" data-tip="Calls link to leads; summaries land in the chatter."><span class="mod-sym">CRM</span><span class="mod-nm">CRM</span><span class="mod-code">connect_<wbr>crm</span></a>
    <a href="Helpdesk/" class="mod-tile" data-cat="app" style="--c:#199e70" data-code="connect_helpdesk" data-label="Odoo apps" data-tip="Match or create tickets by phone number."><span class="mod-sym">HD</span><span class="mod-nm">Helpdesk</span><span class="mod-code">connect_<wbr>helpdesk</span></a>
    <a href="Sales/" class="mod-tile" data-cat="app" style="--c:#199e70" data-code="connect_sale" data-label="Odoo apps" data-tip="Turn a conversation into a quotation or order."><span class="mod-sym">Sal</span><span class="mod-nm">Sales</span><span class="mod-code">connect_<wbr>sale</span></a>
    <a href="Project/" class="mod-tile" data-cat="app" style="--c:#199e70" data-code="connect_project" data-label="Odoo apps" data-tip="Attach conversations to project tasks."><span class="mod-sym">Prj</span><span class="mod-nm">Project</span><span class="mod-code">connect_<wbr>project</span></a>
    <a href="HR/" class="mod-tile" data-cat="app" style="--c:#199e70" data-code="connect_hr" data-label="Odoo apps" data-tip="Employee directory and internal calling."><span class="mod-sym">HR</span><span class="mod-nm">HR</span><span class="mod-code">connect_<wbr>hr</span></a>
    <a href="Accounting/" class="mod-tile" data-cat="app" style="--c:#199e70" data-code="connect_account" data-label="Odoo apps" data-tip="Payment reminders and finance context on the line."><span class="mod-sym">Acc</span><span class="mod-nm">Accounting</span><span class="mod-code">connect_<wbr>account</span></a>
    <a href="customer-memory/admin/memory-setup/" class="mod-tile" data-cat="memory" style="--c:#c98500" data-code="connect_memory" data-label="Memory" data-tip="Hindsight builds durable, long-term memory from every interaction."><span class="mod-sym">Mem</span><span class="mod-nm">Customer Memory</span><span class="mod-code">connect_<wbr>memory</span></a>
    <a href="memory-sales/" class="mod-tile" data-cat="memory" style="--c:#c98500" data-code="connect_memory_sale" data-label="Memory" data-tip="Feeds orders, invoices and payment behaviour into memory."><span class="mod-sym">Ms</span><span class="mod-nm">Memory · Sales</span><span class="mod-code">connect_<wbr>memory_<wbr>sale</span></a>
  </div>
  <div class="mod-tip" id="mod-tip" role="status" aria-live="polite"></div>
</section>

## Architecture

Connect consists of a core module plus provider integrations:

| Module | Purpose |
|--------|---------|
| **connect** | Technology-agnostic core. Stores calls, messages, recordings and users. Handles AI transcription and summarization. |
| **connect_twilio** | Twilio integration. Owns its numbers, extensions, call flows and caller IDs; adds Twilio Voice SDK phone widget, SIP domains, WhatsApp, TwiML apps. |
| **connect_freeswitch** | FreeSWITCH integration. Owns its numbers, extensions, call flows, endpoints and caller IDs; adds Verto WebRTC client, XML dialplan generation, SIP gateways. |
| **connect_asterisk** | Asterisk integration for existing PBXs. Owns its endpoints and DID mappings; adds JsSIP web phone and AMI event pipeline via a sidecar agent. |
| **connect_telnyx** | Telnyx integration. Owns its numbers, extensions, call flows and caller IDs; adds Telnyx WebRTC phone widget, SIP domains (credential connections), TeXML apps, SMS, WhatsApp, RCS. |

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

See the [Admin Guide](Core/admin/installation.md) for detailed setup instructions.
