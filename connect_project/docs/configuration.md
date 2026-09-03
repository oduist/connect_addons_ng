# Configuration & Usage

The Project bridge has **no settings of its own**. Once installed, it works
automatically. This page explains how the automatic linking behaves, the create
button, recordings, and the two shared settings that influence it.

## How tasks and projects are matched

Matching runs inside `connect.call.process_call_event()` — the hook every provider
calls when a call is created — right after the core has recorded the call and
resolved its partner. The lookup tries a task first, then falls back to a project:

1. If the call already has a task or a project, nothing happens (a manual assignment
   is never overwritten).
2. Otherwise, if the call has a **partner**, the module searches for that partner's
   most recent **open task** — a task whose kanban stage is **not folded** (i.e. not
   a Done/Cancelled-style stage). If found, it is attached to the call's `task`
   field.
3. If no open task exists, the module searches for that partner's most recent
   **project** and attaches it to the call's `project` field.

A call therefore ends up with a `task` **or** a `project`, never both.

### Fields added to tasks and projects

Both `project.task` and `project.project` gain `connect_calls` (all linked calls),
the `connect_calls_count` shown on the **Calls** smart button, `recorded_calls`
(recordings whose call is linked here), and read-only `partner_phone` /
`partner_mobile` fields (related to the partner).

## Working with a linked call

On the **Connect call form**:

- The **Project** notebook page shows the linked task and project and an **Unlink**
  button (visible whenever either is set). Unlink clears **both** fields.
- A **Task** stat button (tasks icon) opens the linked task, or — if none is linked
  yet — a new **New Task** form pre-filled with the caller as customer and a name
  like *"Call from &lt;caller&gt;"*. A brand-new task created this way is
  back-linked onto the call automatically (the call id travels in the form context
  and `project.task.create()` reads it).

The call list gains optional `Task` and `Project` columns (right of `Partner`).

On the **task** and **project** forms, a **Calls** smart button (phone icon) opens
all calls linked to that record.

!!! warning "License required for the button"
    The **Task** button raises *"Connect Project license is not activated!"* if the
    license is inactive, because it is a direct user action. The silent automatic
    matching, by contrast, simply skips linking when the license is missing.

## Recorded Calls

The module extends `connect.recording` with `task` and `project` fields. When a
recording is created, it inherits the call's link — the call's task if it has one,
otherwise the call's project. Both the task form and the project form show a
**Recorded Calls** notebook page listing those recordings (start time, caller,
called number, and an inline player).

## Call summaries

If the core OpenAI transcription/summarization feature is enabled and the shared
**Register Summary** setting (`connect.settings.register_summary`) is on, then when a
call gains a summary, that summary is posted to the linked **task** (or the project,
if there is no task) chatter automatically.

!!! info "Register Summary is a core setting"
    `register_summary` lives on the shared `connect.settings` record and governs
    summary posting for **all** Connect bridges, not just Project. Configure it under
    the Connect core settings.

## License gate

Automatic matching, recording links, and summary posting check the Oduist Connect
Project license (`check_license('connect_project')`) silently — if it is not active,
calls are still recorded but nothing is linked and no summary is posted.
