# Oduist Connect Helpdesk — Administrator Guide

`connect_helpdesk` bridges the Oduist Connect telephony core with **Odoo
Helpdesk** (Enterprise). It links telephony calls to helpdesk tickets, can
auto-create tickets from incoming and outgoing calls, and posts OpenAI call
summaries to the linked ticket's chatter.

The module is **provider-agnostic**: it extends the shared Connect ledger
(`connect.call`, `connect.settings`) and the `helpdesk.ticket` model only. It
does not import Twilio, FreeSWITCH or any other provider module, so it works
with whichever telephony provider(s) you have installed and can run alongside
several at once.

## What this module provides

| Area | Capability |
|------|------------|
| **Call ↔ ticket linking** | Adds a `ticket` field to `connect.call` and a `connect_calls` back-reference (with a call-count stat button) to `helpdesk.ticket` |
| **Phone matching** | On each call, matches the caller/called number to an open ticket by normalized phone and attaches it to the call automatically |
| **Auto-create tickets** | Optionally creates a new ticket when a call ends, gated by direction, answered/missed status and unknown-caller rules |
| **Call summaries** | When a call's OpenAI summary is stored, posts it to the linked ticket's chatter (requires the core **Register Summary** setting) |
| **Manual actions** | A **Ticket** button on the call form to create or open a linked ticket, and an **Unlink** action to detach it |

## Dependencies

From `__manifest__.py`:

- **`connect`** — the Oduist Connect telephony core (call ledger, settings,
  OpenAI transcription/summary, licensing).
- **`helpdesk`** — Odoo Helpdesk (Enterprise). The module is not usable on
  Community, where the Helpdesk app is unavailable.

`application` is `False` — this is a bridge module that adds fields, views and
settings to existing apps rather than its own top-level menu.

## Prerequisites

- A running Odoo instance with the core `connect` module installed and at least
  one telephony provider configured, so that `connect.call` records are being
  created.
- The Odoo **Helpdesk** application installed, with at least one team and the
  stages you intend to use.
- A valid Oduist Connect Helpdesk license. Every runtime hook
  (phone matching, auto-create, summary posting, the **Ticket** button) is
  gated on `oduist.license.check_license('connect_helpdesk')`; without an active
  license these behaviours are skipped and the **Ticket** button raises
  *"Connect Helpdesk license is not activated!"*.

## Guide contents

1. [Configuration](configuration.md) — auto-create rules, phone matching, call
   summaries and the manual call/ticket actions.
2. [Security](security.md) — access groups and the webhook access rules.

!!! info "Where things live"
    This module adds no new menus. Its settings appear as a **Helpdesk** page on
    the Connect settings form (**Connect ▸ Configuration ▸ Settings**), the
    call/ticket links appear on the standard **Helpdesk** ticket and Connect
    call forms. Editing the settings requires the **Connect Administrator**
    group (`connect.group_admin`).
