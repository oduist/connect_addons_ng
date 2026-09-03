# Security

The Accounting bridge relies on the Connect security groups defined in the core
module and adds a single access rule of its own.

## Connect groups

| Group | Technical name | Purpose |
|-------|----------------|---------|
| **Connect User** | `connect.group_user` | Read access to Connect records |
| **Connect Administrator** | `connect.group_admin` | Full CRUD on Connect records |
| **Connect Webhook** | `connect.group_webhook` | Identity used by the public webhook controllers that ingest provider events |

The invoice link (`connect.call.invoice`) is a field on `connect.call`, so it
inherits the call's own access rules.

## Webhook access grant

The module grants the webhook identity **read-only** access to `account.move`:

| Model | Read | Create | Write | Unlink |
|-------|:----:|:------:|:-----:|:------:|
| `account.move` | ✓ | — | — | — |

!!! info "Why read-only is enough"
    `process_call_event()` only sets `call.invoice`, a field on `connect.call` that
    the webhook user can already write through core security. The invoice lookup and
    summary posting run with elevated rights, bypassing ACLs. There is no create
    button — invoices are never created from a call — and the **Unlink** action runs
    as the interactive Connect user, not the webhook user. So the webhook identity
    never needs more than read access to `account.move`.
