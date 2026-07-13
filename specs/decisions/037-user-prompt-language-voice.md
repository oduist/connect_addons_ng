# ADR-037: Language and voice for connect.user TTS prompts

## Status
Accepted

## Context

Issue #114: the PBX user form carries two caller-facing text-to-speech
prompts — `greeting_message` and `voicemail_prompt` — but no way to pick
the TTS language or voice for them. Provider callflow models
(`connect.twilio.callflow`, `connect.telnyx.callflow`,
`connect.freeswitch.callflow`) all have a `language` selection (a shared
BCP-47 list of 26 entries, deliberately duplicated per ADR-031) and,
where the provider supports it, a `voice`, and pass them to their Say
rendering. User prompts ignored language/voice entirely:

| Provider | User prompt rendering | Language | Voice |
|---|---|---|---|
| Twilio | `response.say(text)` (`connect_twilio/models/user.py`) | account default | account default |
| Telnyx | `response.say(text)` (`connect_telnyx/models/user.py`) | account default | account default |
| FreeSWITCH | Piper TTS in the user-bridge dialplan (`fs_user.py`) | hardcoded `en-US` | n/a (Piper is language-keyed) |
| Infobip | `POST /calls/1/calls/{id}/say` (`channel.py`) | hardcoded `'en'` | n/a |

`summary_prompt` on `connect.user` is **not** a TTS prompt — it is the
per-user OpenAI GPT prompt for call summaries — so it is out of scope.

Infobip's say is two-phase: `infobip_answer_say_hangup()` stores the text
on the channel and the actual `/say` request is sent later (another
transaction) from `_infobip_flush_pending_say()` when the
CALL_ESTABLISHED webhook arrives, so the language must be persisted on
`connect.channel` alongside the pending text.

## Decision

1. **Core fields on `connect.user`** (the prompts live in core, so their
   TTS attributes do too):
   - `language` — Selection over the same 26-entry BCP-47 list, default
     `en-US`, required. The list becomes the **fourth deliberate copy**
     (ADR-031: no mixins, providers never import core lists and vice
     versa); all four `_get_language_selection()` docstrings and the
     AGENTS.md "deliberately duplicated code" note cross-reference each
     other.
   - `voice` — free-form Char, **no default, not required**. Empty means
     "provider default voice". A core-level default is impossible:
     several providers can be co-installed and Twilio's `Woman` does not
     exist on Telnyx, while `Polly.Joanna` would silently force Polly
     pricing on Twilio users.
2. **Twilio / Telnyx**: user prompt Say gains explicit attributes —
   `language=self.language or 'en-US'` and `voice=self.voice or
   '<provider callflow default>'` (`Woman` for Twilio, `Polly.Joanna`
   for Telnyx) so a user greeting and an IVR prompt in the same call
   sound alike. This intentionally replaces the previous implicit
   account-default voice with an explicit one.
3. **FreeSWITCH**: the user-bridge dialplan context passes
   `voicemail_lang = self.language or 'en-US'` instead of the hardcoded
   `en-US`. The shipped `piper_tts.conf.xml` already has models for all
   26 codes, so no image rebuild is needed.
4. **Infobip**: new `connect.channel.infobip_pending_say_language` field
   persists the language next to `infobip_pending_say`;
   `infobip_answer_say_hangup(text, language='en')` grows a language
   parameter, and `_infobip_flush_pending_say()` sends it. The user
   voicemail fallback maps BCP-47 to Infobip's say codes via a small
   explicit map with a `split('-')[0].lower()` fallback (keeps today's
   `'en'` for the default `en-US`). System apology texts stay English
   (`'en'`).
5. **Asterisk** renders no TTS prompts — untouched.

Rejected alternatives:
- *Per-provider user fields* (`twilio_language`, …) — the prompts
  themselves are single core fields; splitting only their attributes
  per provider multiplies UX for co-installed databases with no benefit.
- *Selection for `voice`* — provider voice catalogs are large, drift
  constantly (Polly/Google generations) and differ per provider; a
  free-form Char with a provider fallback matches the callflow design.
- *Reusing `res.users.lang`* — Odoo UI locales are installed per
  database and do not match the TTS BCP-47 list; a caller-facing prompt
  language is unrelated to the agent's UI language.

## Consequences

- User greeting and voicemail prompts are spoken in the configured
  language/voice on all four voice providers; the form exposes the same
  concept users already know from Call Flows.
- Existing databases: the upgrade creates the columns and Odoo's
  `_init_column` fills `language` with `en-US` for existing rows —
  behaviour is unchanged until an admin picks another language.
- Twilio/Telnyx user prompts now always send explicit
  language/voice attributes instead of inheriting account defaults.
- The BCP-47 list now exists in four copies (core + 3 providers); a
  change to one must be applied to all in the same commit (ADR-031
  discipline, documented in AGENTS.md).
- The Infobip say-language map is best-effort verified; unmapped codes
  degrade to the base subtag, never breaking the call flow.
