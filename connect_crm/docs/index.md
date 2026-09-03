# Oduist Connect CRM — Administrator Guide

`connect_crm` bridges the Oduist Connect telephony core with Odoo **CRM**. It
links telephone calls to `crm.lead` opportunities, can auto-create leads from
inbound and outbound calls, attributes calls to UTM sources by phone number, and
posts AI call summaries to the linked lead's chatter.

The module is **provider-agnostic**: it extends only the shared ledger models
(`connect.call`, `connect.settings`) and never imports a specific telephony
provider. It works the same whether calls arrive through Twilio, FreeSWITCH,
Telnyx, Asterisk or any other Connect provider, and it can be installed
alongside one or several of them at once.

## What this module provides

| Area | Capability |
|------|------------|
| **Call ↔ Lead linking** | Each `connect.call` gets a `lead` field; calls are matched to existing open leads by caller/called number while the call is still ringing. |
| **Auto-create leads** | Optionally create a lead (or opportunity) when a call ends, with independent rules for incoming/outgoing and answered/missed calls. |
| **UTM attribution** | A phone number can be attached to a `utm.source`; inbound calls to that number set the call's (and any created lead's) source. |
| **Lead UI** | A "Calls" stat button on the lead form, a "CRM" tab and "Lead" button on the call form, and lead/source columns in the call list. |
| **Call summaries** | When core produces an OpenAI call summary, it is posted to the linked lead's chatter. |
| **Message routing** | Inbound messages can create/route to leads — the Twilio-specific glue lives in the auto-installed `connect_crm_twilio` bridge. |

## Dependencies

From `__manifest__.py`:

- **`connect`** — the telephony core (shared call ledger and settings).
- **`crm`** — Odoo CRM (`crm.lead`, `crm.stage`, `crm.team`).
- **`utm`** — Odoo UTM (`utm.source`) for phone-based call attribution.

!!! note "Provider modules are not a dependency"
    You need at least one Connect provider module (Twilio, FreeSWITCH, Telnyx,
    …) installed to actually place or receive calls, but `connect_crm` itself
    does not depend on any of them.

## Prerequisites

- A running Odoo instance with the core `connect` module installed and a
  telephony provider configured.
- The **CRM** and **UTM** apps installed (pulled in automatically as
  dependencies).
- A valid Oduist Connect license — CRM behavior (matching, auto-create, summary
  posting) is gated on `check_license('connect_crm')`. Without a valid license
  the overrides fall through and do nothing.

## Guide contents

1. [Configuration & Lead Routing](configuration.md) — auto-create rules, UTM
   source attribution, call/lead matching, and call summaries.
2. [Security](security.md) — access groups and webhook permissions.

!!! info "Menu location"
    CRM auto-create settings live on the **CRM** tab of the core settings form
    (**Connect ▸ Configuration ▸ Settings**, Connect Administrator only).
    Call-to-lead links appear on the standard **CRM** and **Connect** call
    screens; UTM phone numbers are edited under the standard Odoo UTM sources.
