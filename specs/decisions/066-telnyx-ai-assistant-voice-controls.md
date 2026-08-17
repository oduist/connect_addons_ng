# ADR-066: Manage Telnyx AI assistant voice controls in Odoo

## Status

Accepted.

## Context

Telnyx AI Assistant `voice_settings` supports provider-neutral controls in
addition to the voice identifier and speaking speed. Two controls are relevant
to the multilingual receptionist flow:

- `language_boost` hints or automatically selects the synthesis language;
- `expressive_mode` lets supported voices, including Telnyx Ultra, add
  contextual expression.

Odoo currently publishes only `voice` and `voice_speed`. Administrators must
therefore edit the missing settings outside Odoo, even though Odoo is the
authoritative source for assistant configuration. A later Odoo update uses a
partial Telnyx payload and normally preserves those remote-only values, but a
recreated assistant cannot restore them.

Not every TTS provider supports expressive mode, and existing assistants may
rely on provider defaults for language handling. New fields must therefore not
silently enable provider-specific behavior for every assistant.

Official references:

- https://developers.telnyx.com/api-reference/assistants/create-an-assistant
- https://developers.telnyx.com/docs/voice/tts/providers/telnyx/ultra

## Decision

Add `language_boost` and `expressive_mode` to
`connect.telnyx.ai_assistant` and expose both fields in the Model and Voice
section of the assistant form.

`language_boost` is optional. When it is empty, Odoo omits the key so Telnyx
keeps the provider or account default. Administrators may use `auto` for a
multilingual voice or an explicit provider-supported language hint.

`expressive_mode` defaults to disabled and is always published as a Boolean.
Administrators enable it only for a voice that Telnyx documents as expressive.

Both fields participate in automatic synchronization, manual Push to Telnyx,
and remote-value normalization. When Telnyx rejects a configured voice and
Odoo falls back to the known AWS Polly voice, the retry disables expressive
mode and omits the language boost because the fallback voice must remain a
safe compatibility path.

This decision does not add `llm_api_key_ref`. Telnyx documentation and Portal
availability for third-party LLM secrets must be reconciled separately before
Odoo stores or publishes that credential reference.

## Consequences

- Odoo can recreate the selected multilingual and expressive voice behavior.
- Existing assistants keep provider-default language handling until an
  administrator explicitly fills `language_boost`.
- Expressive mode remains opt-in and does not affect existing non-expressive
  voices by default.
- The fallback voice retry remains valid even when the rejected voice used
  expressive or multilingual settings.
- Third-party LLM secret management remains outside the scope of this change.

## Amendment 2026-08-17: guarded voice speed range

A live assistant configured with `voice_speed = 2.0` on a `Telnyx.Ultra.*`
voice answered every call and hung up after one second:
`CallStatus=conversation_ended`, `Reason=greeting_error`, zero messages, and
`GET /ai/conversations/<id>` reporting "The assistant could not generate the
greeting audio." Probing `POST /v2/text-to-speech/speech` with that voice
returned `400` code `90103` at 0.5 and at 1.8 or more, and audio between 0.8
and 1.5; the documented `[0.25, 2.0]` range covers Telnyx Natural voices only.

Odoo therefore constrains `voice_speed` to `[0.5, 1.5]` and clamps a remote
value into the same range, so an unsupported speed is refused in the form
instead of producing an assistant that is silently unusable on every call.
The bounds are an administrative guard, not a per-voice capability table:
Telnyx publishes no machine-readable range per voice, so the field help
carries the remaining warning that Telnyx Ultra needs at least 0.8.

Surfacing a Telnyx `greeting_error` in the Odoo call ledger — today such a
call is only a short `completed` entry — remains open.
