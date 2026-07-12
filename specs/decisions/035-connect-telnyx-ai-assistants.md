# 035: Telnyx AI Assistants remain behind the Odoo TeXML router

## Context

Telnyx can assign a number directly to an AI Assistant, but `connect_telnyx`
already attaches every number to one routing TeXML application. Direct
assignment would bypass the provider's destination selection, call ledger,
partner matching, webhook verification and coexistence with users/callflows.

## Decision

1. AI Assistants are managed as `connect.telnyx.ai_assistant` records. Odoo
   creates, updates, imports and deletes the corresponding `/v2/ai/assistants`
   resources.
2. A number with destination `ai_assistant` stays attached to the existing
   routing TeXML application. Its render result is
   `<Connect><AIAssistant id="…"/></Connect>`.
3. Caller context is supplied by a signed dynamic-variables webhook. Mutable
   Odoo operations use per-assistant random tool tokens and a fixed allowlist;
   arbitrary model access and server actions are not exposed.
4. Voice conversations are synchronized into `connect.call` and a
   `connect.recording` record with `source=telnyx-ai`. Transcript and native
   Telnyx summary are idempotently refreshed by webhook plus cron fallback.
5. Recording and cross-conversation memory are opt-in. Telephony is enabled;
   assistant messaging is outside this change.

## Consequences

- Existing Telnyx destinations and call accounting remain compatible.
- Odoo's public URL and Ed25519 public key must be configured before assistant
  synchronization.
- CRM and Helpdesk tools appear only when their companion modules are installed.
- Inline webhook tools are limited to per-assistant Odoo endpoints whose token
  cannot be shared safely in the global Telnyx tool library.
