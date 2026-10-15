# Agent Tools & Setup

This add-on installs four agent tools. All are `connect.elevenlabs_agent_tool`
records of type **webhook**; each maps to a `/connect_elevenlabs_sale/*` HTTP
route. Parameters are sent in the request **body** and each tool has a 20-second
response timeout.

## Tools

### get_products

Returns the catalog the agent can sell. Route:
`POST /connect_elevenlabs_sale/get_products`.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `category_id` | integer | no | Present in the tool definition; the current implementation returns all published products regardless of category |

Only **published** product templates are returned. For each, the response
includes the **product variant id** (`product_id`), the template id, name, public
categories, list price, sale description, and a fixed `items_in_stock` of 10.

!!! warning "`items_in_stock` is a placeholder"
    The stock figure is hard-coded to `10` in the controller — it is not a real
    availability check. Do not rely on it for stock decisions.

### create_sale_order

Creates a `sale.order` for the caller. Route:
`POST /connect_elevenlabs_sale/create_order`.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `product_id` | integer | yes | Product **variant** id returned by `get_products` |
| `product_quantity` | integer | yes | Ordered quantity (defaults to 1 if absent) |
| `partner_id` | integer | yes | The caller's partner |

The order is created with a single line for the given variant at its list price;
invoice/shipping addresses default to the partner when those fields exist.
Returns the new `order_name` (e.g. `S00001`). If the product id is not found, the
tool returns an error message instead.

### get_sale_order_info

Fetches detail for one order. Route:
`POST /connect_elevenlabs_sale/get_order`.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `partner_id` | integer | yes | The caller's partner |
| `order_name` | string | yes | Order reference, e.g. `S00001` |

Both parameters are required; the search is scoped to the partner's own orders.
Returns each matching order's id, number, delivery/commitment date, shipping
weight, the salesperson's name, and that salesperson's **Twilio extension**
(`user.connect_user.twilio_exten.number`, or `No extension`), plus the order
lines (product name and quantity).

### get_sale_orders

Lists a partner's order references. Route:
`POST /connect_elevenlabs_sale/get_orders`.

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `partner_id` | integer | yes | The caller's partner |

Returns the list of order names for the partner. Returns an error message if no
partner id is supplied or no orders exist.

## Authentication

All four routes are `type='http'`, `auth='public'`, `csrf=False`, and begin by
calling `check_tool_token()` (inherited from the connect_elevenlabs base
controller). The request must carry the `x-elevenlabs-agent-token` header equal
to the configured **Agent Token** (`elevenlabs_agent_token` in settings);
otherwise the controller raises `401 Unauthorized`. This is the same shared
secret connect_elevenlabs sends when it registers the tools with ElevenLabs.

The controllers act with `sudo()`, so all sale operations run with the elevated
webhook identity — access is gated entirely by the token, not by a user's Odoo
groups. This add-on ships **no** `ir.model.access` rows of its own.

!!! warning "Keep the API URL and token consistent"
    ElevenLabs stores each tool's callback URL when the tool is synced. If the
    Odoo public **API URL** or the **Agent Token** changes, re-sync the tools
    from the ElevenLabs settings form so the stored URLs and secret match.

## Setup checklist

1. Install **Sales** and **eCommerce**; publish the products you want the agent
   to offer. Install and configure **connect_elevenlabs** (API key, Agent Token,
   public API URL).
2. Install `connect_elevenlabs_sale`.
3. Open an ElevenLabs agent and add the four sale tools on its **Tools** tab
   (with a suitable sales system prompt).
4. **Sync** the tools and the agent to ElevenLabs from the ElevenLabs settings
   form.
5. Point an inbound number / extension at the agent and place a test call:
   list products, create an order, then confirm it appears under **Sales**
   linked to the caller.

## Tests

The module includes `tests/test_sale_tools.py` (`HttpCase`) covering the four
routes: that `get_products` returns the variant id, `create_order` uses the
variant and quantity, `get_order` reports the salesperson's Twilio extension,
and `get_orders` works without a call id. Run with
`oduflow run_odoo_tests connect_elevenlabs_sale`.
