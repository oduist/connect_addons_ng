# Security

The Project bridge relies on the Connect security groups defined in the core module
and adds two access rules of its own.

## Connect groups

| Group | Technical name | Purpose |
|-------|----------------|---------|
| **Connect User** | `connect.group_user` | Read access to Connect records |
| **Connect Administrator** | `connect.group_admin` | Full CRUD on Connect records |
| **Connect Webhook** | `connect.group_webhook` | Identity used by the public webhook controllers that ingest provider events |

The task and project links (`connect.call.task`, `connect.call.project`) are fields
on `connect.call`, so they inherit the call's own access rules.

## Webhook access grants

The module grants the webhook identity **read-only** access to both target models:

| Model | Read | Create | Write | Unlink |
|-------|:----:|:------:|:-----:|:------:|
| `project.task` | ✓ | — | — | — |
| `project.project` | ✓ | — | — | — |

!!! info "Why read-only is enough"
    `process_call_event()` only sets `call.task` / `call.project`, fields on
    `connect.call` that the webhook user can already write through core security —
    it only **links** existing records, never creates them. The lookup searches run
    with elevated rights, bypassing ACLs. The recording link writes
    `connect.recording` fields, not the task/project themselves, and summary posting
    runs as superuser. The **Task** button and the **Unlink** action run as the
    interactive Connect user, not the webhook user. So the webhook identity never
    needs more than read access to `project.task` and `project.project`.

!!! note "Creating tasks from a call"
    A user who creates a task via the call form does so with their **own** Project
    permissions. If they lack the right to create tasks, that action is blocked by
    the Project security model, independently of this bridge.
