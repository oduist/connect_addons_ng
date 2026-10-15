# Oduist Connect ElevenLabs Sales — Administrator Guide

`connect_elevenlabs_sale` is an add-on for **connect_elevenlabs** (the
ElevenLabs Conversational-AI voice-agent add-on for Twilio). It lets an
ElevenLabs voice agent act as a sales assistant on a live call: list the
published catalog, create a sale order for the caller, and look up the caller's
existing orders.

The module ships no new models, menus or web views. It contributes a set of
**agent tools** (`connect.elevenlabs_agent_tool` records) and the HTTP **webhook
controllers** those tools call back into Odoo.

## What this module adds on top of connect_elevenlabs

| Area | Capability |
|------|------------|
| **Catalog** | Agent retrieves the **published** (website-published) products with price, description, public categories and variant id |
| **Order creation** | Agent creates a `sale.order` for the caller's partner with a chosen product variant and quantity |
| **Order lookup** | Agent lists a partner's order references, or fetches one order's lines, delivery date, weight and the assigned salesperson's Twilio extension |

## Dependencies

From `__manifest__.py`:

```python
"depends": ['connect_elevenlabs', 'sale_management', 'website_sale']
```

- **connect_elevenlabs** — the ElevenLabs agent add-on (agents, tools, agent
  token, tool webhook base controller). Configure and connect this first.
- **sale_management** — Odoo Sales (`sale.order`, quotations, salespeople).
- **website_sale** — eCommerce; provides the **is_published** flag and public
  product categories the catalog tool relies on.

!!! note "Only published products are offered"
    `get_products` returns product templates where `is_published` is true (their
    website "Published" toggle). Products that are not published on the website
    are invisible to the voice agent.

## Prerequisites

- A working **connect_elevenlabs** setup: a valid ElevenLabs API key, the
  **Agent Token** (`elevenlabs_agent_token`) generated in the ElevenLabs
  settings, and the public **API URL** configured so tool callbacks resolve to a
  reachable HTTPS Odoo endpoint.
- Sales and eCommerce configured, with the products you want the agent to sell
  **published** on the website.
- A **publicly reachable HTTPS URL for Odoo** — ElevenLabs invokes each tool as
  a server-side webhook back into this instance.

## How it works

1. The tools defined in `data/tools.xml` are created as
   `connect.elevenlabs_agent_tool` records on install.
2. An administrator adds the tools to an ElevenLabs agent and **syncs** the
   agent/tools to ElevenLabs from the ElevenLabs settings form.
3. During a call, the agent invokes a tool. ElevenLabs POSTs to the matching
   `/connect_elevenlabs_sale/*` route with the shared `x-elevenlabs-agent-token`
   header.
4. The controller validates the token (`check_tool_token`), performs the sale
   operation with `sudo()`, and returns a JSON result the agent reads back to
   the caller.

The module also registers a `post_init_hook` that refreshes the Oduist license
status on install; it does not affect runtime behavior.

See [Agent Tools & Setup](tools.md) for the tool reference, callback routes,
security and configuration steps.

!!! info "Menu location"
    This add-on adds no menu of its own. Its tools appear under the existing
    **Connect ▸ ElevenLabs** screens provided by connect_elevenlabs. Managing
    agents and tools requires the **Connect Administrator** group
    (`connect.group_admin`).
