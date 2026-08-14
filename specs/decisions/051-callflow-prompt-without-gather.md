# ADR-051: Keep the call-flow prompt visible without Gather

**Status:** Accepted
**Date:** 2026-08-14

## Context

Twilio call flows use `prompt_message` in two modes. With Gather enabled, the
message is nested in TwiML `<Gather>` and introduces the available choices.
With Gather disabled, the same message is emitted as a standalone `<Say>`
before the flow rings its users or continues to its fallback. The form hid the
Prompt Message together with Gather-only fields, so administrators could hear a
configured message that they could not see or edit.

## Decision

Always display Prompt Message on the Twilio call-flow form. Continue hiding
Gather Settings, Invalid Input Message, Choices, and other input-specific
configuration while Gather Input is disabled. Place Invalid Input Message in
the same row as Gather Settings because both configure the input-collection
phase. Display Prompt Message in its own full-width section below that row.

The rendering behavior remains unchanged: a non-empty prompt is played in both
modes, while Gather Input only controls whether Twilio collects DTMF or speech.

## Consequences

- The form accurately exposes every prompt that callers can hear.
- Ring-group-only flows can configure a greeting without enabling input.
- Gather-only validation and choice fields remain out of the way when unused.
- Related Gather configuration is visually grouped in one row.
