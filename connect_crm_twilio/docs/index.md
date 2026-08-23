# Oduist Connect CRM Twilio Bridge — Administrator Guide

`connect_crm_twilio` is a tiny **glue module** between the Connect CRM bridge and
the Twilio integration. It exists so that Twilio's inbound message routing can
target CRM leads while keeping `connect_crm` itself provider-agnostic (ADR-031).

There is nothing to configure in this module — it is installed automatically and
simply adds one routing option.

## What it does

The module contributes a single model extension: it adds **CRM Lead** as a
destination on Twilio's message-configuration model.

- `_inherit = 'connect.twilio.message_configuration'`
- Adds `('crm.lead', 'CRM Lead')` to the `destination` selection (with
  `ondelete = 'set default'`).

With the bridge installed, a Twilio message configuration can route an inbound
SMS/WhatsApp message to a **CRM Lead** — creating or matching a lead by the
sender's phone number via the lead-lookup logic provided by `connect_crm`
(`crm.lead.create_record_from_message()` / `get_lead_by_number()`).

## Dependencies

From `__manifest__.py`:

- **`connect_crm`** — the CRM bridge that owns the `crm.lead` linking and
  lookup logic.
- **`connect_twilio`** — the Twilio integration that owns
  `connect.twilio.message_configuration`.

## Installation

!!! info "Auto-installed"
    `auto_install: True` — this module installs itself automatically as soon as
    **both** `connect_crm` and `connect_twilio` are present in the database. You
    do not install or upgrade it directly; it follows its two parents.

It ships no data, no views, no security rules and no menus of its own. The **CRM
Lead** routing option appears wherever Twilio message configurations are
edited (under the **Connect ▸ Twilio ▸ Messages** configuration screens).

## Prerequisites

- Both `connect_crm` and `connect_twilio` installed and configured.
- A configured Twilio number/messaging setup so that inbound messages reach a
  Twilio message configuration to route.
