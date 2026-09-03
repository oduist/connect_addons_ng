# Security

The Sales bridge relies on the Connect security groups defined in the core module
and adds a single access rule of its own.

## Connect groups

| Group | Technical name | Purpose |
|-------|----------------|---------|
| **Connect User** | `connect.group_user` | Read access to Connect records |
| **Connect Administrator** | `connect.group_admin` | Full CRUD on Connect records |
| **Connect Webhook** | `connect.group_webhook` | Identity used by the public webhook controllers that ingest provider events |

The order link (`connect.call.sale_order`) is a field on `connect.call`, so it
inherits the call's own access rules.

## Webhook access grant

The module grants the webhook identity **read-only** access to `sale.order`:

| Model | Read | Create | Write | Unlink |
|-------|:----:|:------:|:-----:|:------:|
| `sale.order` | ✓ | — | — | — |

!!! info "Why read-only is enough"
    `process_call_event()` only sets `call.sale_order`, a field on `connect.call`
    that the webhook user can already write through core security. The partner
    lookup and summary posting run with elevated rights, bypassing ACLs. The
    **Sale Order** button and the **Unlink** action run as the interactive Connect
    user — with that user's own rights on `sale.order`, granted separately through
    the Sales app's security groups — not the webhook user. So the webhook identity
    never needs more than read access to `sale.order`.

!!! note "Creating orders from a call"
    A user who creates a sale order via the call form does so with their **own**
    Sales permissions. If they lack the right to create sale orders, that action is
    blocked by the Sales security model, independently of this bridge.
