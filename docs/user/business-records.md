# Calls and Business Records

Connect can attach every call to the Odoo record it belongs to — an employee,
a sale order, an invoice, a project task, a CRM lead or a helpdesk ticket.
The link is made automatically while the call is being processed, so the call
history on a customer record fills itself in without anyone tagging calls by
hand.

Each integration ships as its own module. Install only the ones you need:

| Module | Links calls to | Menu where the calls appear |
|--------|----------------|-----------------------------|
| **Oduist Connect HR** | Employees | Employee form → **Calls** |
| **Oduist Connect Sale** | Sale orders | Sale order form → **Calls** |
| **Oduist Connect Account** | Customer invoices | Invoice form → **Calls** |
| **Oduist Connect Project** | Tasks and projects | Task/project form → **Calls** |
| **Oduist Connect CRM** | Leads and opportunities | Lead form → **Calls** |
| **Oduist Connect Helpdesk** | Tickets | Ticket form → **Calls** |

## How a call finds its record

Matching runs once per call, right after the call is registered. A call that
already points at a record is never re-assigned, so a manual correction stays
in place.

| Module | Matching rule |
|--------|---------------|
| **HR** | By phone number. An incoming call is matched on the caller's number, an outgoing call on the number dialled, against the employee's work and mobile phone. |
| **Sale** | By customer. The call is attached to that customer's most recent sale order. |
| **Account** | By customer. The call is attached to the customer's newest **posted, unpaid customer invoice**. Vendor bills are never matched. |
| **Project** | By customer. The call is attached to the customer's newest task in an open stage; if the customer has no open task, it is attached to their project instead. |

If nothing matches, the call is simply left unlinked — you can still attach it
by hand from the call form.

## What you see

**On the business record** — a **Calls** button in the button box opens the
full call history for that record. On projects and tasks there is also a
**Recorded Calls** tab listing the recordings made during those calls.

**On the call** — the linked record appears in its own field on the call form
(**Employee**, **Sale Order**, **Invoice**, **Task**, **Project**) and as a
column you can enable in the call list. Next to the field, **Unlink** detaches
the call from the record without deleting either.

## Creating a record from a call

Some modules can create the record straight from the call, which is the usual
way to handle a call from someone who is not in the system yet:

- **Project** — **Create Task** on the call form.
- **Sale** — **Create Sale Order** on the call form.
- **CRM** — **Create Lead**.
- **Helpdesk** — **Create Ticket**.

The buttons are idempotent: pressing one a second time opens the record that
was already created rather than making a duplicate. The new record is linked
to the call, and the customer is carried over when the call has one.

HR and Account have no such button by design — employees and invoices are not
things you create from an inbound call.

## Call summaries on the record

When AI call summaries are switched on (**Connect > Configuration > Settings**,
*Register call summary*), the summary of a finished call is posted to the
chatter of the linked record as soon as it is generated. That puts the gist of
the conversation on the invoice, task or employee file without anyone
re-typing it.

Summaries are only posted to records the call is actually linked to. See
[Recordings & Transcriptions](recordings.md) for how summaries are produced.

## Licensing

Each of these modules is licensed separately from the Connect core. When a
module's licence is missing or expired, its linking, buttons and summary
posting stop quietly — calls are still recorded and the rest of Connect keeps
working.
