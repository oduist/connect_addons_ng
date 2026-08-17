# 062: Telnyx AI receptionists use Odoo-owned extensions and transfer tools

## Context

Telnyx AI Assistants were reachable only through public numbers. The module
also imported unknown assistants from Telnyx and then partially rewrote their
configuration, which made the ownership of prompts and tools ambiguous.

The required receptionist flows are broader:

- a personal assistant answers a manager's public number, qualifies the call,
  and transfers only after learning the reason;
- a company assistant replaces an IVR and routes to configured departments;
- SIP and WebRTC users can call an assistant directly by extension;
- a warm transfer briefs the recipient before the caller is bridged;
- caller personalization is safe only when one Odoo contact matches the
  caller number;
- an offline SIP/WebRTC registration must not be presented as an available
  human transfer target.

Telnyx exposes live registration state through
`GET /v2/sip_registration_status`. Both hardphones and the Telnyx WebRTC SDK
use per-device telephony credentials, so their `sip_username` values can be
queried with `credential_type=telephony_credential`. Registration is only an
advisory signal: a registered device can still be busy, rejected, or fail to
answer.

Telnyx's shared Transfer tool supports dynamic targets, SIP URIs, and warm
transfer instructions. The built-in `telnyx_agent_target` variable is a valid
`from` value for both calls to a public number and calls to a SIP extension.

## Decision

1. Odoo is the source of truth for assistants managed by
   `connect.telnyx.ai_assistant`. Account sync pushes local assistants and
   never imports unknown remote assistants. The manual **Pull from Telnyx**
   action is removed. Unknown remote resources are left untouched.
2. An assistant can own a `connect.telnyx.exten` back-link and a Telnyx domain.
   The domain TeXML router resolves the extension and renders the same
   `<Connect><AIAssistant>` response used by public-number routing.
3. Receptionists have two routing modes:
   - **Personal**: one configured `connect.user` manager;
   - **Company**: configured `connect.telnyx.callflow` departments, whose
     `ring_users` become human transfer candidates.
   Existing models are reused; no generic model access or arbitrary tool
   execution is introduced.
4. Odoo manages one shared Telnyx Transfer tool per assistant. Its target list
   is the dynamic variable `{{transfer_targets}}`, its `from` value is
   `{{telnyx_agent_target}}`, and its warm-transfer instructions require a
   concise briefing with the confirmed caller identity, reason, context, and
   agreed next step.
5. Transfer targets point directly at the selected registered telephony
   credential (`sip:<username>@sip.telnyx.com`). This ensures the warm briefing
   reaches the human recipient rather than an intermediate TeXML router.
   Credential priority follows the user's configured SIP/WebRTC priorities.
6. When presence checking is enabled, definitely unregistered credentials are
   omitted. An API timeout or status error is treated as unknown and falls
   back to the configured credential, so a Telnyx status outage cannot disable
   all routing. No-answer handling remains the assistant's responsibility.
7. Caller matching for AI personalization is strict. The raw and E.164 lookup
   may identify a contact only when their combined result contains exactly one
   `res.partner`. Multiple matches return an ambiguous result and no name.
   When one candidate exists, the prompt requires verbal confirmation before
   the assistant treats the identity as verified.
8. The receptionist policy requires the assistant to say that it can register
   a request or connect the caller, determine the reason before any transfer,
   and offer request registration when no human target is available.
9. Odoo Contact, CRM, and Helpdesk actions remain signed, fixed allowlist
   webhook tools. Telnyx conversation memory remains opt-in and is separate
   from Odoo's `connect_memory` module.

## Consequences

- An external phone number is not required for an internal SIP/WebRTC call to
  an assistant.
- Company routing reuses callflows as department definitions and their users
  as transfer recipients; managers configure extensions and telephony
  credentials before enabling transfers.
- Presence checks improve routing but do not guarantee that a person answers.
- Manually created Telnyx assistants and tools are no longer copied into Odoo.
  Administrators create and edit managed assistants in Odoo and push them to
  Telnyx.
- Existing imported assistant rows remain usable for compatibility, but no new
  rows are imported and their Odoo configuration becomes authoritative on the
  next push.
