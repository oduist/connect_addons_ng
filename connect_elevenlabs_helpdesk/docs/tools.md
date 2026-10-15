# Agent Tools & Setup

This add-on installs five agent tools and one agent template. All tools are
`connect.elevenlabs_agent_tool` records of type **webhook**; each maps to a
`/connect_elevenlabs_helpdesk/*` HTTP route.

## The Helpdesk Support Agent template

`data/agent_templates.xml` ships one `connect.elevenlabs_agent_template` record,
**Helpdesk Support Agent**. Its system prompt instructs the voice agent to
create tickets, search and fetch tickets, update them and add notes, and it
documents the priority levels and stage names. The prompt references the runtime
variables `{{partner_id}}`, `{{call_id}}` and `{{system__time}}`, which
ElevenLabs injects per call.

Apply the template when creating an agent, then attach the tools below (Tools
tab of the agent) and sync the agent to ElevenLabs.

## Tools

Each tool sends its parameters in the request **body** and has a 20-second
response timeout. Parameters marked *dynamic* are injected automatically by
ElevenLabs from the conversation context (they are **not** asked of the caller).

### helpdesk_create_ticket

Creates a new `helpdesk.ticket`. Route: `POST /connect_elevenlabs_helpdesk/create_ticket`.

| Parameter | Type | Required | Source |
|-----------|------|----------|--------|
| `subject` | string | yes | agent (becomes the ticket name; defaults to *"Ticket from phone call"*) |
| `description` | string | no | agent |
| `team_name` | string | no | agent — matched `ilike` against `helpdesk.team` names |
| `partner_id` | integer | no | dynamic variable `partner_id` |
| `call_id` | integer | yes | dynamic variable `call_id` |

The partner is taken from `partner_id` if given, otherwise from the call's
partner. The new ticket copies the partner's email/phone, is linked back to the
`connect.call` (`call.ticket`), and the ticket is created with the
`connect_call_id` context. Returns `ticket_id`, `ticket_number`, `ticket_name`.

### helpdesk_search_tickets

Lists the caller's tickets. Route: `POST /connect_elevenlabs_helpdesk/search_tickets`.

| Parameter | Type | Required | Source |
|-----------|------|----------|--------|
| `partner_id` | integer | yes | dynamic variable `partner_id` |
| `only_open` | boolean | no | agent — when true, filters to unfolded (open) stages |

Returns up to 10 tickets (newest first) with id, name, stage, create date and
description.

### helpdesk_fetch_ticket

Fetches full detail for one ticket. Route: `POST /connect_elevenlabs_helpdesk/fetch_ticket`.

| Parameter | Type | Required | Source |
|-----------|------|----------|--------|
| `ticket_id` | integer | yes | agent |

Returns name, description, stage, partner name/email/phone, team, assigned user,
create date and priority.

### helpdesk_update_ticket

Updates an existing ticket. Route: `POST /connect_elevenlabs_helpdesk/update_ticket`.

| Parameter | Type | Required | Source |
|-----------|------|----------|--------|
| `ticket_id` | integer | yes | agent |
| `subject` | string | no | agent |
| `description` | string | no | agent |
| `priority` | string | no | agent — `0` Low, `1` Medium, `2` High, `3` Urgent |
| `stage_name` | string | no | agent — matched `ilike` against `helpdesk.stage` names |

At least one updatable field must be provided.

### helpdesk_ticket_activity

Posts a note/comment on a ticket. Route: `POST /connect_elevenlabs_helpdesk/ticket_activity`.

| Parameter | Type | Required | Source |
|-----------|------|----------|--------|
| `ticket_id` | integer | yes | agent |
| `note` | string | yes | agent |

The note is added with `message_post` as a `comment`, useful for logging call
summaries on the ticket.

## Authentication

All five routes are `type='http'`, `auth='public'`, `csrf=False`, and begin by
calling `check_tool_token()` (inherited from the connect_elevenlabs base
controller). The request must carry the `x-elevenlabs-agent-token` header equal
to the configured **Agent Token** (`elevenlabs_agent_token` in settings);
otherwise the controller raises `401 Unauthorized`. This is the same shared
secret connect_elevenlabs sends when it registers the tools with ElevenLabs.

!!! warning "Keep the API URL and token consistent"
    ElevenLabs stores each tool's callback URL when the tool is synced. If the
    Odoo public **API URL** or the **Agent Token** changes, re-sync the tools
    from the ElevenLabs settings form so the stored URLs and secret match.

## Security

`security/webhook.xml` grants the webhook identity group
(`connect.group_webhook`) the access it needs — the controllers run under
`sudo()`, and these ACLs back that access:

| Model | Read | Write | Create | Unlink |
|-------|:----:|:-----:|:------:|:------:|
| `helpdesk.ticket` | yes | yes | yes | no |
| `helpdesk.team` | yes | no | no | no |
| `helpdesk.stage` | yes | no | no | no |

No `connect.group_user` or `connect.group_admin` rows are added by this add-on;
agent and tool administration continues to use the groups defined by
connect_elevenlabs (admin-managed).

## Setup checklist

1. Install **Helpdesk** and at least one team; install **connect_elevenlabs** and
   complete its ElevenLabs configuration (API key, Agent Token, public API URL).
2. Install `connect_elevenlabs_helpdesk`.
3. Create or open an ElevenLabs agent; apply the **Helpdesk Support Agent**
   template (optional) and add the five helpdesk tools on the agent's **Tools**
   tab.
4. **Sync** the tools and the agent to ElevenLabs from the ElevenLabs settings
   form.
5. Point an inbound number / extension at the agent and place a test call:
   create a ticket, then confirm it appears under **Helpdesk** linked to the
   caller and to the call.
