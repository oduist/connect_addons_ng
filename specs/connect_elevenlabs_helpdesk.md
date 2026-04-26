# Connect ElevenLabs Helpdesk Module Specification

## Module Info

- **Name:** Oduist Connect ElevenLabs Helpdesk
- **Technical:** `connect_elevenlabs_helpdesk`
- **Version:** 19.0.1.0.0
- **Depends:** `connect_elevenlabs`, `connect_helpdesk`
- **Application:** False
- **License:** Other proprietary

## Overview

Adds helpdesk-specific ElevenLabs agent tools so a conversational-AI agent can create and search helpdesk tickets during a call. Extends the agent-tool webhook controller from `connect_elevenlabs`.

## Models

No new models. Relies on `connect_helpdesk.ticket` and the `connect.call.ticket` relation already provided by `connect_helpdesk`.

## Controllers (connect_elevenlabs_helpdesk/controllers/)

### main.py — `ConnectElevenlabsHelpdeskController(ConnectElevenlabsController)`

Reuses `check_tool_token()` from the base controller and inherits `dispatch()` (which enforces license via `check_license('connect_elevenlabs_helpdesk', silent=False)`).

Routes (all `type=jsonrpc` on Odoo 19+, `auth=public`, `csrf=False`, `x-elevenlabs-agent-token` header required):

- `POST /connect_elevenlabs_helpdesk/create_ticket` — body: `call_id`, optional `partner_id`, optional `team_name`, `subject`, `description`, `email`, `phone`. Creates a `helpdesk.ticket`, links it to the call via `call.ticket`, returns `{ticket_id, ticket_number, ticket_name, message}`.
- `POST /connect_elevenlabs_helpdesk/search_tickets` — body: `partner_id`, optional `only_open`. Returns up to 10 tickets with `ticket_id`, `ticket_name`, `stage`, `create_date`, etc.

## Data

- `tools.xml` — seed `connect.elevenlabs_agent_tool` records for `helpdesk_create_ticket` and `helpdesk_search_tickets` with their `connect.agent_tool_params` rows.
- `agent_templates.xml` — starter agent template configured with the helpdesk tools pre-selected.

## Security

- `security/webhook.xml` — access rules for `connect.user_connect_webhook` to create/write `helpdesk.ticket` via the controller.

## License

`settings.py` (one-liner) appends `'connect_elevenlabs_helpdesk'` to `ODUIST_MODULES`. All enforcement happens through the inherited `dispatch()`.
