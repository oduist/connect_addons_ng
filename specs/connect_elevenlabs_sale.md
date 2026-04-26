# Connect ElevenLabs Sale Module Specification

## Module Info

- **Name:** Oduist Connect ElevenLabs Sale
- **Technical:** `connect_elevenlabs_sale`
- **Version:** 19.0.1.0.0
- **Depends:** `connect_elevenlabs`, `sale_management`
- **Application:** False
- **License:** Other proprietary

## Overview

Adds sale-order-aware context and tools to ElevenLabs conversational-AI agents so the agent can look up products, quote prices, or surface sale-order information during a call.

## Models (connect_elevenlabs_sale/models/)

### 1. call.py — `_inherit = 'connect.call'`

Overrides `elevenlabs_agent_get_call_data()` to enrich the call-context payload sent to the media bridge with a `sale_module_extra_prompt` entry (empty by default; overridable by downstream customisations). License check via `check_license('connect_elevenlabs_sale', silent=True)` — falls back to `super()` when inactive.

## Controllers (connect_elevenlabs_sale/controllers/)

### main.py

Sale-specific webhook tools, all `type=jsonrpc` on Odoo 19+, `auth=public`, `csrf=False`, `x-elevenlabs-agent-token` header required. Routes match those declared in `data/tools.xml` (product lookup, sale-order creation/query).

## Data

- `tools.xml` — seed `connect.elevenlabs_agent_tool` records for the sale tools with their `connect.agent_tool_params` rows.

## Settings

`settings.py` (one-liner): appends `'connect_elevenlabs_sale'` to `ODUIST_MODULES`.

## Post-init Hook

`post_init_hook(env)` resets `create_date` on the module record and calls `env['oduist.license'].update_license_status(raise_exc=False)` — same shape as the other `connect_elevenlabs_*` modules.

## License

Enforced via `check_license('connect_elevenlabs_sale', silent=True)` in the call data extension; controller dispatch inherits enforcement from the base `connect_elevenlabs` controller.
