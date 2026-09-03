# Security

The HR bridge relies on the Connect security groups defined in the core module and
adds a single access rule of its own.

## Connect groups

| Group | Technical name | Purpose |
|-------|----------------|---------|
| **Connect User** | `connect.group_user` | Read access to Connect records |
| **Connect Administrator** | `connect.group_admin` | Full CRUD on Connect records |
| **Connect Webhook** | `connect.group_webhook` | Identity used by the public webhook controllers that ingest provider events |

The employee link (`connect.call.employee`) is a field on `connect.call`, so it
inherits the call's own access rules — a Connect User can read it and a Connect
Administrator can change or unlink it.

## Webhook access grant

The module grants the webhook identity **read-only** access to `hr.employee`:

| Model | Read | Create | Write | Unlink |
|-------|:----:|:------:|:-----:|:------:|
| `hr.employee` | ✓ | — | — | — |

!!! info "Why read-only is enough"
    `process_call_event()` only sets `call.employee`, a field on `connect.call`
    that the webhook user can already write through core security. The lookup is a
    plain search and never creates or writes an employee. Summary posting runs with
    elevated rights, and the **Unlink** action runs as the interactive Connect user,
    not the webhook user. So the webhook identity never needs more than read access
    to `hr.employee`.
