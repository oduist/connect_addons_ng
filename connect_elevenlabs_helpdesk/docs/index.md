# Oduist Connect ElevenLabs Helpdesk — Administrator Guide

`connect_elevenlabs_helpdesk` is an add-on for **connect_elevenlabs** (the
ElevenLabs Conversational-AI voice-agent add-on for Twilio). It lets an
ElevenLabs voice agent read and write Odoo **Helpdesk** tickets during a live
phone call, so callers can open, look up, update and comment on support tickets
by talking to the agent.

The module ships no new models, menus or web views. It contributes:

- a set of **agent tools** (`connect.elevenlabs_agent_tool` records) that expose
  helpdesk operations to a voice agent;
- the HTTP **webhook controllers** those tools call back into Odoo;
- a ready-made **agent template** with a helpdesk system prompt;
- the **webhook access rights** needed to touch helpdesk records.

## What this module adds on top of connect_elevenlabs

| Area | Capability |
|------|------------|
| **Ticket creation** | Agent creates a `helpdesk.ticket` from the call, links it to the caller's partner and to the `connect.call`, optionally routing it to a named helpdesk team |
| **Ticket lookup** | Agent searches the caller's existing tickets (optionally only open ones) and fetches full detail for a single ticket |
| **Ticket updates** | Agent changes a ticket's subject, description, priority or stage by name |
| **Ticket notes** | Agent logs a comment / call summary on a ticket via `message_post` |
| **Agent template** | "Helpdesk Support Agent" system prompt wired to the five tools above |

## Dependencies

From `__manifest__.py`:

```python
"depends": ['connect_elevenlabs', 'connect_helpdesk']
```

- **connect_elevenlabs** — the ElevenLabs agent add-on (agents, tools, agent
  token, tool webhook base controller). Configure and connect this first.
- **connect_helpdesk** — the Oduist Connect helpdesk bridge, which in turn pulls
  in Odoo's **Helpdesk** application.

!!! warning "Enterprise Helpdesk required"
    Odoo's `helpdesk` module is an **Enterprise** application. This add-on can
    only be installed on an Odoo edition that includes Helpdesk (`helpdesk.team`,
    `helpdesk.ticket`, `helpdesk.stage`). On Community it will not install.

## Prerequisites

- A working **connect_elevenlabs** setup: a valid ElevenLabs API key, the
  **Agent Token** (`elevenlabs_agent_token`) generated in the ElevenLabs
  settings, and the public **API URL** configured so tool callbacks resolve to a
  reachable HTTPS Odoo endpoint.
- The **Helpdesk** application installed and at least one helpdesk team.
- A **publicly reachable HTTPS URL for Odoo** — ElevenLabs invokes each tool as
  a server-side webhook back into this instance.

## How it works

1. The tools defined in `data/tools.xml` are created as
   `connect.elevenlabs_agent_tool` records on install.
2. An administrator adds the tools (or applies the **Helpdesk Support Agent**
   template) to an ElevenLabs agent and **syncs** the agent/tools to ElevenLabs
   from the ElevenLabs settings form.
3. During a call, the agent invokes a tool. ElevenLabs POSTs to the matching
   `/connect_elevenlabs_helpdesk/*` route, sending the shared
   `x-elevenlabs-agent-token` header.
4. The controller validates the token (`check_tool_token`), performs the
   helpdesk operation with `sudo()`, and returns a JSON result the agent reads
   back to the caller.

See [Agent Tools & Setup](tools.md) for the tool reference, the callback routes,
security and configuration steps.

!!! info "Menu location"
    This add-on adds no menu of its own. Its tools and the agent template appear
    under the existing **Connect ▸ ElevenLabs** screens provided by
    connect_elevenlabs. Managing agents and tools requires the **Connect
    Administrator** group (`connect.group_admin`).
