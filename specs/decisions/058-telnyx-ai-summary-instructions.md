# ADR-058: Editable Telnyx AI summary instructions

## Problem

Calls handled by a Telnyx AI assistant are summarized by Telnyx, not by the
core OpenAI path: `connect.settings.summary_prompt` has no effect on them. The
prompt of the Telnyx conversation insight that produces those summaries was a
literal inside `connect.telnyx.ai_assistant._ensure_summary_group()`, so an
administrator could not change the focus or the language of the summary from
Odoo.

The insight is also created once and cached by ID
(`telnyx_ai_summary_insight_id`), so even editing the literal in the source had
no effect on an account that had already synchronized.

## Options

1. **Leave it hardcoded**, tell administrators to edit the insight in Mission
   Control. Keeps Odoo simple, but the wording then lives outside the database,
   is lost on a fresh install, and silently diverges between environments.
2. **Expose the text and `PUT`/`PATCH` the existing insight.** One remote call,
   the insight ID never changes. Telnyx does not consistently document an update
   endpoint for conversation insights across API versions, so this couples the
   feature to an endpoint we cannot rely on.
3. **Expose the text and recreate the insight on change.** Delete the stored
   insight, clear the ID and let the existing `_ensure_summary_group()` create a
   new one and assign it to the surviving insight group. Uses only endpoints the
   module already calls.

## Decision

Option 3.

`connect.settings.telnyx_ai_summary_instructions` (Text, required, default =
the previous literal, now `DEFAULT_AI_SUMMARY_INSTRUCTIONS` in
`connect_telnyx/models/settings.py`) is shown in the Telnyx settings form under
**AI Assistants**. Writing it triggers
`_refresh_telnyx_ai_summary_insight(instructions)`:

- no stored insight ID → do nothing; the next account sync creates the insight
  from the stored text;
- otherwise `DELETE ai/conversations/insights/{id}` best-effort — a failure is
  logged, not raised, because an orphaned remote insight is cheaper than a
  refused save — then the ID is cleared and `_ensure_summary_group(instructions)`
  recreates and re-assigns the insight.

The insight **group** is never recreated: it carries the webhook URL Telnyx
posts summaries to, and reusing it keeps that endpoint stable.

The new text is passed as an argument rather than read back through
`get_param()`, matching `_push_telnyx_outbound_destinations()`: the hook runs
inside `write()`, before the registry cache is cleared.

## Consequences

- Summaries generated before the change keep their original wording; Telnyx
  applies the new instructions only to conversations analysed afterwards.
- Changing the prompt allocates a new insight ID. The old insight is deleted
  where the API allows it; when the delete fails, an unused insight is left in
  the Telnyx account and must be removed manually if it matters.
- Speech recognition stays per assistant (`transcription_language`,
  `transcription_model`) — this decision covers the summary only.
- The core OpenAI transcription path is untouched: `summary_prompt` and
  `openai_summary_model` still govern non-AI-assistant recordings, and the
  OpenAI transcription language remains auto-detected.
