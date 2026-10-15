# Configuration & Lead Routing

This page covers how `connect_crm` turns calls into leads: the auto-create
settings, UTM phone attribution, how existing leads are matched to live calls,
and how AI call summaries reach the lead chatter.

## Auto-create settings

Open **Connect ▸ Configuration ▸ Settings** (Connect Administrator only) and
switch to the **CRM** tab. These options are stored on the shared
`connect.settings` singleton.

### Incoming calls

| Field | Default | Description |
|-------|---------|-------------|
| **Auto Create Leads** (`auto_create_leads_for_in_calls`) | Off | Master toggle for incoming calls. When off, no lead is auto-created for inbound calls. |
| **For Answered Calls** (`auto_create_leads_for_in_answered_calls`) | On | Create a lead when an incoming call completed (was answered). |
| **For Not Answered Calls** (`auto_create_leads_for_in_missed_calls`) | On | Create a lead when an incoming call did not complete (missed). |
| **For Unknown Callers** (`auto_create_leads_for_in_unknown_callers`) | Off | Create a lead even for numbers not found in Contacts. |

### Outgoing calls

| Field | Default | Description |
|-------|---------|-------------|
| **Auto Create Leads** (`auto_create_leads_for_out_calls`) | Off | Master toggle for outgoing calls. |
| **For Answered Calls** (`auto_create_leads_for_out_answered_calls`) | On | Create a lead when an outgoing call completed. |
| **For Not Answered Calls** (`auto_create_leads_for_out_missed_calls`) | On | Create a lead when an outgoing call did not connect. |

!!! note "Calls to internal users are skipped"
    Outgoing calls that reach a local PBX user (`called_pbx_users`) never
    auto-create a lead — only external destinations do.

### Options

Shown only when at least one auto-create master toggle is on.

| Field | Description |
|-------|-------------|
| **Default Salesperson** (`auto_create_leads_sales_person`) | Fallback salesperson (`res.users`, non-shared) assigned to the lead when the call has no resolved PBX user. |
| **Leads type** (`auto_create_leads_type`) | Create a `lead` or an `opportunity`. Required; defaults to **Lead**. |

## How auto-create works

Auto-create runs once, in `register_call()`, **when the call has fully ended** —
never during ringing. The direction and final status of the call then select a
rule:

=== "Incoming"

    1. The master **Auto Create Leads** toggle must be on.
    2. `completed` calls need **For Answered Calls**; non-completed calls need
       **For Not Answered Calls**; otherwise **For Unknown Callers** is the last
       fallback.
    3. The salesperson is taken from the answering PBX user, then the first
       called PBX user, then the **Default Salesperson**.
    4. The lead name is the matched partner's name, or the caller number; the
       caller number is stored as the lead `phone` when there is no partner.

=== "Outgoing"

    1. The master **Auto Create Leads** toggle must be on.
    2. Calls that reached a local PBX user are skipped.
    3. `completed` calls need **For Answered Calls**; non-completed calls need
       **For Not Answered Calls**.
    4. The salesperson is the calling user, then the **Default Salesperson**.
    5. The lead name is the partner name or the called number; the called number
       is stored as `phone` when there is no partner.

If a call already has a lead linked, auto-create does nothing.

## UTM source attribution

Attach a phone number to a marketing source so inbound calls to that number are
credited to it.

- Edit a **UTM Source** (standard Odoo UTM app) and set its **Phone** field. The
  number is unique across sources — reusing one raises *"This phone number is
  already used!"*.
- On an incoming call, Connect looks up the source whose **Phone** equals the
  *called* number and sets the call's `source`.
- When a lead is auto-created (or created from the call form) the matched source
  is copied to the lead's **Source**, so campaign reporting attributes the
  opportunity correctly.

## Matching existing leads to live calls

While a call is still active (`process_call_event()`), `connect_crm` tries to
attach an existing **open** lead so it is visible in the active-calls widget:

- Incoming calls match on the **caller** number; outgoing calls match on the
  **called** number.
- `get_lead_by_number()` searches active leads in non-won stages (or with no
  stage) by normalized `phone`/`mobile`, trying the stripped number, a
  `+`-prefixed variant, and the E.164 form.
- Very short or `unknown` numbers are skipped. If several leads match, the most
  recent is used and a warning is logged.

Matching only **links** an existing lead; it never creates one. Creation is the
job of the auto-create rules above (or manual creation from the call form).

## Working with leads and calls in the UI

- **Lead form** — a **Calls** stat button (phone icon) shows the number of
  linked calls and opens the filtered call list.
- **Lead search** — the CRM leads filter gains **Phone** and **Mobile** search
  fields.
- **Call form** — a **Lead** button creates or links a lead (reusing an existing
  match when one is found), and a **CRM** tab shows the linked **Lead** and
  **Source** with an **Unlink** button.
- **Call list** — a **Lead** column (shown by default) and an optional
  **Source** column (hidden by default).

## Call summaries to the lead chatter

When core transcription/summarization is enabled (the **Register Summary**
setting) and a call has both a summary and a linked lead, the summary is posted
to that lead's chatter automatically. This is driven by a constraint on the
call's `summary` field, so it fires as soon as the summary is written.
