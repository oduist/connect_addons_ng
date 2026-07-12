# 033: connect_telnyx — WhatsApp & RCS messaging

## Problem

ADR-032 shipped connect_telnyx without WhatsApp/RCS. The owner asked to
close that gap, mirroring the connect_twilio WhatsApp feature set where
Telnyx supports it, and adding RCS (which Twilio does not have).

Telnyx surfaces:

- **WhatsApp**: `/v2/whatsapp/phone_numbers` (senders with editable
  business profile), `/v2/whatsapp/business_accounts` (WABAs),
  `/v2/whatsapp/message_templates` (create/list, Meta approval status),
  `POST /messages/whatsapp` (text/template/media content). Unlike
  Twilio there is no `whatsapp:` address prefix — plain +E.164 — and
  inbound/status events arrive on the SAME messaging-profile webhook as
  SMS (v2 JSON envelopes with `payload.type = 'whatsapp'`).
- **RCS**: agents provisioned per account
  (`/messaging/rcs/agents`), rich send via `POST /messages/rcs`
  (`agent_message.content_message`, optional `sms_fallback`/
  `mms_fallback`), capability lookup per number. Inbound arrives as
  `message.received` with `payload.type = 'RCS'`.

## Decisions

1. **Models mirror the Twilio shapes, prefixed per ADR-031/032**
   (Twilio owns the unprefixed `connect.whatsapp_sender` /
   `connect.message_content_template` / `connect.whatsapp_composer`):
   - `connect.telnyx.whatsapp_sender` — synced from
     `whatsapp.phone_numbers.list()` + `…profile.retrieve()`;
     profile fields are editable and pushed back via
     `profile.update()`; `no_sync`, `is_default`, link to
     `connect.telnyx.number`. `send_whatsapp()` creates the
     `connect.message` (type `WhatsApp`) + chatter like Twilio's.
   - `connect.telnyx.whatsapp_template` — synced from
     `whatsapp.templates.list()`; `create_in_telnyx()` submits a
     body-only template for Meta approval (`whatsapp.templates.create`);
     status/rejection_reason are read back by sync. The body preview /
     `{{n}}` variable machinery is ported from the Twilio template
     model.
   - `connect.telnyx.whatsapp_composer` — transient wizard (sender,
     phone, template + variables JSON with live preview, body).
   - `connect.telnyx.rcs_agent` — synced read-only from
     `messaging.rcs.agents.list()`; `is_default`; `send_rcs()` sends
     `content_message.text` with an SMS fallback and logs a
     `connect.message` (type `RCS`).
   - `connect.telnyx.rcs_composer` — transient wizard (agent, phone,
     body, optional SMS-fallback toggle).

2. **24-hour window rule.** Freeform WhatsApp sends are refused unless
   an inbound WhatsApp message from the recipient exists within 24h
   (local ledger check, same heuristic as connect_twilio); template
   sends are always allowed. Telnyx's `conversation_window` endpoint is
   noted but not relied on until verified live.

3. **No WhatsApp voice calls.** Telnyx exposes WhatsApp Business
   Calling settings, but its interplay with TeXML is unverified —
   voice stays out of scope (messaging only). No `whatsapp_call` branch
   in `originate_call`, no `<WhatsApp>` dial noun.

4. **Inbound/status routing stays on the single messaging webhook.**
   `connect.message.telnyx_receive()` maps `payload.type`:
   `whatsapp` → `WhatsApp`, `RCS` → `RCS`, else `sms`. Status events
   (`message.sent`/`message.finalized`) already update by `message_sid`;
   a failed WhatsApp/RCS send posts a chatter note like Twilio's status
   callback handler.

5. **User preference.** `connect.user.telnyx_whatsapp_sender_id`
   mirrors Twilio's `whatsapp_sender_id`; `get_default_sender()` order:
   user preference → `is_default` → any.

6. **Frontend parity.** `telnyx-whatsapp-reply` message action (opens
   the Telnyx WhatsApp composer), a WhatsApp *Message* button on the
   phone field widget, and the Notification icon patch for the
   `WhatsApp`/`RCS` notification types (stacking-safe when
   connect_twilio also patches).

7. **Access rights** mirror the Twilio matrix: senders — user R /
   admin CRUD / webhook R; templates — user R / admin CRUD; RCS agents
   — user R / admin CRUD; composers — user CRUD (transient).

## Consequences

- `telnyx_sync()` additionally syncs WhatsApp senders, WhatsApp
  templates and RCS agents; sync failures there are non-fatal (logged,
  reported) because accounts commonly have no WhatsApp/RCS onboarding.
- Menu: Connect > Telnyx > Messages gains WhatsApp Senders, WhatsApp
  Templates and RCS Agents (admin) plus composer wizards.
- Live verification against an onboarded WhatsApp/RCS Telnyx account is
  required (payload shapes for inbound WhatsApp/RCS, template component
  format, fallback billing) — same caveat class as ADR-032 §5/§6.
- Module version stays 19.0.1.0.0 — the module has not shipped yet;
  this lands in the same release unit as ADR-032.
