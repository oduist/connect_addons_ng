# ADR-057: Manage Telnyx AI assistant voice controls in Odoo

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

## Amendment 2026-08-18: catalog-backed voice selection and sample playback

`voice` was a free-form Char, so the assistant form showed the raw identifier
an administrator had to copy from the Telnyx portal — for a cloned voice a
bare UUID such as `Telnyx.Ultra.00a77add-…`. The account catalog and its
filtered autocomplete already existed for System Voice (ADR-052), which is
why the assistant now reuses them instead of growing a second mechanism:

1. The `telnyx_voice` widget takes the names of its filter fields as options,
   defaulting to the System Voice ones. The assistant adds `voice_language`
   and `voice_provider`: computed from the selected voice, `store=True` and
   `readonly=False`, so they follow a voice change but keep a filter the
   administrator picked for a voice Odoo cannot resolve. Neither field is
   published to Telnyx.
2. The assistant reads the catalog without the basic TeXML voices (`man`,
   `woman`, `alice`): they are part of the `<Say>` contract and cannot drive
   an assistant. A voice whose language or provider Telnyx leaves empty now
   matches every filter — a cloned voice is otherwise unreachable in both
   selectors.
3. `language_boost` becomes a Selection over the language list Telnyx
   documents for `voice_settings`. That list is a closed enum, unlike the
   voice catalog whose drift is what ADR-052 rejected a Selection for. An
   unknown remote value is dropped on read rather than failing the sync.
4. Expressive mode is only offered while a `Telnyx.Ultra.*` voice is
   selected, and clears itself when the voice moves to another provider.
   Because the switch is then invisible, the payload publishes it as `false`
   for a voice without expressive support and an imported `true` on such a
   voice is dropped on read: a hidden field must not keep sending a value
   the administrator can no longer see. The same reasoning drops a stored
   `language_boost` that is not part of the published language list.
5. A speaker button synthesizes a sample through
   `POST /v2/text-to-speech/speech` (`output_type=base64_output`) with the
   configured voice and speed and plays it in the browser. This is the same
   validation path that fails an assistant greeting, so the pair that ends
   every call after one second is now refused while the form is open. Speed
   is sent only inside the provider object that documents it
   (`telnyx`/`rime` `voice_speed`, `minimax` `speed`); other providers reject
   an unknown key. A greeting containing dynamic variables is replaced by a
   standard sentence so the sample does not read out `{{...}}`.

Access decision: the catalog lookups and the sample live on
`connect.telnyx.ai_assistant`, which `connect.group_user` may read, and they
call the admin-only `connect.settings` with `sudo()`. Read-only lookups stay
open to any Connect user because they expose nothing but voice names, while
`telnyx_preview_voice` requires `connect.group_admin`: each call spends
Telnyx text-to-speech credit. Widening access to `connect.settings` itself
was rejected — it holds the API key and every provider credential. The same
group check guards the `connect.settings` entry point: `call_kw` refuses
private method names only and runs no access check of its own, so an
admin-only model ACL does not stop an authenticated session from calling a
public method that works through `sudo()`.

Voice previews are not cached in Odoo and are not stored as attachments; the
audio is returned to the browser and discarded.
