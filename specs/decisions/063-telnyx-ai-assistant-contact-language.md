# ADR-063: Telnyx AI assistant contact-language greeting

## Status

Accepted.

## Context

Telnyx AI Assistants separate speech recognition, language-model behavior,
and text-to-speech synthesis. A transcription language such as `en` only
configures speech recognition; it does not force the LLM to answer in that
language and it does not make an English-only voice multilingual.

Telnyx documents the following relevant capabilities:

- `deepgram/nova-3` is the recommended multilingual transcription model and
  supports automatic language detection when `transcription.language` is
  omitted or set to `auto`;
- `deepgram/flux` supports `auto`, `multi`, and a smaller explicit language
  set;
- assistant instructions and greetings accept dynamic variables resolved by
  a webhook before the conversation starts;
- a TTS voice must support the language it is asked to speak. MiniMax and
  Inworld are explicitly multilingual, and the voice catalog also exposes
  Azure multilingual voices.

Odoo already stores the preferred language on `res.partner.lang`, and the
Telnyx assistant variables webhook performs a strict phone lookup that only
returns a partner when exactly one record matches. That lookup is the right
place to select a caller language without weakening the duplicate-number
safety introduced by ADR-062.

Official references:

- https://developers.telnyx.com/api-reference/assistants/create-an-assistant
- https://developers.telnyx.com/docs/inference/ai-assistants/dynamic-variables
- https://developers.telnyx.com/docs/voice/tts/available-voices

## Decision

Each `connect.telnyx.ai_assistant` has a language mode and a fallback Odoo
language:

- **Contact, then automatic** uses the unique matched partner's language,
  falling back to the assistant language when no unique contact language is
  available. After the greeting, the assistant may follow a caller who
  clearly speaks another language.
- **Fixed** always uses the assistant language.
- **Automatic** starts in the assistant language and then follows the language
  detected from the caller's speech.

The default mode is Contact, then automatic. The default transcription
configuration for newly created assistants is `deepgram/nova-3` with
`language=auto`.

The assistant payload templates its greeting with `{{odoo_initial_greeting}}`
and defines an assistant-level fallback equal to the configured greeting.
The dynamic variables webhook overrides that value per call, so a webhook
timeout still produces a valid greeting rather than speaking an unresolved
placeholder.

For a unique contact, Odoo supplies:

- the Odoo locale and normalized BCP-47 language code;
- a human-readable language name;
- whether the language came from the contact, assistant fallback, or automatic
  mode;
- a localized receptionist greeting where an Odoo translation is installed.

The effective instructions require the LLM to begin in the selected language,
confirm a matched identity, and follow an explicit caller language change when
the mode permits it. Ambiguous phone matches continue to expose no identity or
contact language.

Odoo does not automatically switch a single-language TTS voice. Administrators
must choose a multilingual voice for a single consistent speaker across
languages, or configure separate assistants when language-specific voices are
preferred.

## Consequences

- Known callers can hear the first greeting in their Odoo contact language
  before speaking.
- Unknown callers still receive a deterministic greeting and can be handled by
  automatic multilingual transcription.
- Activating a language in Odoo and setting it on the contact becomes the
  source of truth for caller preference.
- `transcription.language=auto` is required for broad language switching; a
  fixed transcription language intentionally constrains recognition.
- Voice quality depends on the selected TTS voice's actual language coverage,
  independently of the LLM and transcription settings.
