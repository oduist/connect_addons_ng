# Oduist Connect Project — Administrator Guide

`connect_project` is a **provider-agnostic bridge** that links calls in the Oduist
Connect telephony platform to Odoo project tasks and projects. When a call is
recorded, the module looks up an open task for the call's partner (falling back to a
project) and attaches it to the `connect.call`. From a call you can also open — or
create — a task in one click, and call recordings surface directly on the linked
task or project.

Because the bridge depends only on the shared `connect.call` ledger — never on a
specific telephony provider — it works identically for calls handled through
Twilio, FreeSWITCH, Asterisk, Telnyx, Infobip, or any other Connect provider. All
providers funnel their events through the same `connect.call.process_call_event()`
hook, and this module extends that hook.

## What this module provides

| Area | Capability |
|------|------------|
| **Call linking** | Automatically attaches an open **task** (primary) or **project** (fallback) to each call, matched by the call's **partner** |
| **Create from call** | A **Task** stat button on the call form opens the linked task, or a new task pre-filled for the caller |
| **Task / Project form** | A **Calls** smart button and a **Recorded Calls** page on both the task and project forms; partner phone/mobile shown read-only |
| **Call form** | A **Project** notebook page shows the linked task and project, with an **Unlink** action |
| **Call list** | Optional `Task` and `Project` columns on the Connect call list |
| **Recordings** | Call recordings inherit the call's task/project link, populating the **Recorded Calls** pages |
| **Summaries** | Optionally posts the OpenAI call summary to the linked task (or project) chatter |

!!! info "Two targets, mutually exclusive"
    This is the only one of the Connect app bridges with **two** target models. A
    call links to a **task** *or* a **project**, never both — an open task always
    wins over a project. Matching is by the call's **partner**.

## Dependencies

From `__manifest__.py`:

- `connect` — the Oduist Connect core (shared call ledger).
- `project` — Odoo Project.

## Prerequisites

- The core `connect` module installed and configured with at least one telephony
  provider.
- Core partner matching working, so calls carry a `partner` for the lookup to use.
- A valid Oduist Connect Project license. Automatic matching checks the license
  silently; the **Task** button raises an error if the license is not active.

## Guide contents

1. [Configuration & Usage](configuration.md) — how task/project matching works, the
   create button, recordings, summary posting, and the license gate.
2. [Security](security.md) — access groups and the webhook grants.

!!! note "Menus"
    This bridge adds **no menu of its own**. Linked calls surface on the existing
    **Connect** call views and through the **Calls** smart button on each task and
    project. Configuration lives on the shared Connect settings.
