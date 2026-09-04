# Webhooks & Security

## Public URL requirement

Twilio delivers every voice/message/recording event to Odoo over HTTP webhooks.
Your Odoo instance **must be reachable from the internet over HTTPS**. Set the
core **API URL** (**Connect ▸ Configuration ▸ Settings**) to the public URL —
Connect builds every webhook URL it pushes to Twilio from this value.

Twilio requires HTTPS for signature validation; if Odoo is only reachable over
plain HTTP, signature checks fail and the log shows *"Twilio requires HTTPS to be
setup!"*.

## Webhook routes

All routes are under `/twilio/webhook/`, declared `type='http'`, `auth='public'`,
`csrf=False`, and run as the dedicated webhook user
(`connect.user_connect_webhook`).

| Route | Purpose |
|-------|---------|
| `POST /twilio/webhook/callstatus` | Call status callbacks (initiated / answered / completed). |
| `POST /twilio/webhook/callaction` | Call action handling. |
| `POST /twilio/webhook/<model_name>/call_action/<record_id>` | Model-specific call action (legacy `connect.callflow` names are remapped to `connect.twilio.callflow`). |
| `POST /twilio/webhook/number` | Inbound call to a Twilio number → routes to destination. |
| `POST /twilio/webhook/twiml/<twiml_id>` | Renders a TwiML application. |
| `POST /twilio/webhook/callflow/<flow_id>/gather` | Call-flow `<Gather>` result (DTMF/speech). |
| `POST /twilio/webhook/domain` | Inbound SIP-domain call routing. |
| `POST /twilio/webhook/recordingstatus` | Recording status callback. |
| `POST /twilio/webhook/vm_recordingstatus` | Voicemail recording callback. |
| `POST /twilio/webhook/message` | Incoming SMS / WhatsApp. |
| `POST /twilio/webhook/message_status` | Message delivery status. |
| `POST /twilio/webhook/outgoing_callerid` | Caller-ID validation status. |

## Signature validation

Every webhook first runs `check_signature()`:

- When **Verify Twilio Requests** (`twilio_verify_requests`) is **on** (the
  default), the controller validates the `X-Twilio-Signature` header with
  `twilio.request_validator.RequestValidator`, using the **Auth Token** read via
  `sudo()`. The request URL is forced to `https:` for the signature computation.
- `check_signature()` validates against the **POST form body only**
  (`request.httprequest.form`), never the merged route kwargs: Twilio signs the
  full URL (query string included) plus the POST parameters, and Odoo folds the
  query string into the kwargs, so validating with those would count every query
  parameter twice and reject any webhook URL that carries one.
- When validation fails, voice endpoints return `<Response><Say>Invalid Twilio
  request!</Say></Response>` and status endpoints return `False`; nothing is
  processed.
- When the option is **off**, validation is skipped (development only — keep it
  **on** in production).

!!! danger "Do not disable verification in production"
    With verification off, anyone who can reach the public webhook URLs can
    inject call/message/recording events. Only turn it off temporarily for local
    debugging.

## Security groups & access

The module reuses the core Connect groups:

- **Connect User** (`connect.group_user`) — read access to Twilio config models.
- **Connect Administrator** (`connect.group_admin`) — full CRUD; required for the
  Configuration menu, WhatsApp senders/templates, and message configuration.
- **Connect Webhook** (`connect.group_webhook`) — the identity of the public
  webhook controllers.

Model access (`security/access_rules.xml`):

| Model | User | Admin | Webhook |
|-------|------|-------|---------|
| `connect.twilio.exten` | Read | Full | Read |
| `connect.twilio.callflow` | Read | Full | Read |
| `connect.twilio.callflow_choice` | Read | Full | Read |
| `connect.twilio.number` | Read | Full | Read |
| `connect.twilio.outgoing_callerid` | Read | Full | Read + Write |
| `connect.twilio.user_callflow` | Read | Full | — |
| `connect.twilio.user_callflow_call` | Read | Full | — |
| `connect.twilio.message_configuration` | — | Full | — |
| `connect.twilio.twiml` | Read | Full | Read |
| `connect.twilio.domain` | Read | Full | Read |
| `connect.whatsapp_sender` | Read | Full | Read + Write + Create |
| `connect.message_content_template` | Read | Full | — |

The **Auth Token** and **API Secret** are additionally protected at the field
level (`base.group_erp_manager` only) and are never returned to the webhook
identity; they are masked (`****`) for non-managers.
