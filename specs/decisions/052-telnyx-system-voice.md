# 055 - Telnyx system voice for TeXML Say

## Status

Accepted

## Context

Telnyx TeXML accepts a `voice` attribute on `<Say>`. The current Telnyx
module sets it for user greetings, user voicemail prompts, and callflow
prompts, but its routing errors, service notices, custom TeXML, and TeXPy
responses commonly omit it. Those messages therefore use Telnyx's implicit
default and can sound different from the configured prompts in the same
call.

The Telnyx voice catalog is not a stable enum. The `Say` contract accepts
basic voices (`man`, `woman`, `alice`) and provider-prefixed identifiers such
as `Polly.VoiceId`, `AWS.Polly.VoiceId`, `Azure.VoiceId`, and
`Telnyx.ModelId.VoiceId`. Telnyx also exposes the account's current catalog
through `GET /v2/text-to-speech/voices`; the response can include pre-built,
third-party, and account-scoped cloned voices.

## Decision

1. Add an admin-only Telnyx setting named `System Voice`, defaulting to the
   module's existing `Polly.Joanna` fallback.
2. Present the catalog as a three-step selector: `System Voice Language`,
   `System Voice Provider`, and `System Voice`. Cache the account catalog
   returned by `GET /v2/text-to-speech/voices`, refresh it during the normal
   Telnyx account sync, and provide a dedicated refresh button. Build the
   language and provider selections from that cache, using readable labels
   instead of raw API values.
3. Implement `System Voice` as a server-backed autocomplete filtered by the
   selected language and provider. Return only a bounded number of matching
   voices and show their name, gender, and technical Telnyx identifier. Store
   only the identifier required by `<Say voice="...">`. Keep the basic TeXML
   voices, `Polly.Joanna`, and the currently selected value available even
   when the API is unavailable or the remote catalog changes.
4. Before a TeXML response leaves the module, parse it and add the system
   voice to every `<Say>` that has no `voice` attribute. Preserve an explicit
   per-prompt voice unchanged. Apply the same finalization to custom TeXML,
   TeXPy output, model-method applications, and direct webhook responses.
5. Replace the hardcoded Telnyx user-prompt fallback with `System Voice`.
   Make the callflow voice optional and use `System Voice` when no callflow
   override is configured.
6. Treat catalog refresh as optional during the full account sync: a catalog
   failure is logged but does not prevent numbers, domains, or messaging
   resources from synchronizing. The dedicated refresh action still reports
   an API failure to the administrator.

Rejected alternatives:

- A hardcoded Selection of provider voices would drift as Telnyx adds or
  removes models and could never include account-scoped cloned voices.
- A flat Selection containing the complete catalog makes Odoo send thousands
  of options as field metadata, mixes languages and providers in one menu,
  and is too slow and difficult to navigate.
- A free-form Char would accept the complete Telnyx contract but would not
  give administrators the requested filtered list of voices available to
  their account.
- Overwriting explicit user or callflow voices would remove the existing
  per-prompt control and make those fields misleading. The system voice is a
  complete fallback, not a forced override.

## Consequences

- Every runtime Telnyx `<Say>` has a deterministic voice while explicit
  prompt-level choices keep precedence.
- The settings form offers readable language and provider filters without a
  network request every time the form opens.
- Voice search transfers only the matching subset instead of embedding the
  full account catalog in the form metadata.
- A newly added or cloned voice appears after refreshing the catalog or
  running the normal Telnyx sync.
- Existing callflows keep their stored `Polly.Joanna` value. Administrators
  can clear it when they want the callflow to follow future System Voice
  changes.
- Malformed non-XML output remains unchanged so the voice finalizer cannot
  hide the original TeXML error.
