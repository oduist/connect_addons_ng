# ADR-050: Configurable OpenAI summary model

**Status:** Accepted
**Date:** 2026-08-16

## Context

Core call summarization is hard-coded to `gpt-4o` unless the deployment sets the
undocumented `OPENAI_COMPLETION_MODEL` environment variable. Administrators cannot
see or change the active summary model from Connect settings, and new installations
do not use the requested GPT-5.4 mini model by default.

OpenAI documents `gpt-5.4-mini` as a Chat Completions-compatible model. The existing
summary integration can therefore keep its current API while exposing the model as
normal Connect configuration.

## Decision

Add a required `openai_summary_model` selection to `connect.settings` with these
choices:

- `gpt-5.4-mini` (GPT-5.4 mini), selected by default;
- `gpt-4o` (GPT-4o), retained for existing workflows that need the previous model.

The selected model is shown on the core Transcription settings tab and is used by
`connect.recording.make_summary()`. `OPENAI_COMPLETION_MODEL` remains an optional
deployment-level override and takes precedence when set, preserving existing hosted
configuration.

GPT-5-family Chat Completions use `max_completion_tokens`; legacy models keep the
existing `max_tokens` and sampling parameters. This avoids sending legacy-only
parameters to GPT-5.4 mini while leaving GPT-4o behavior unchanged.

## Consequences

- New and upgraded databases default call summaries to GPT-5.4 mini.
- Administrators can switch between GPT-5.4 mini and GPT-4o without changing the
  service environment.
- Deployments that already set `OPENAI_COMPLETION_MODEL` continue to override the UI
  selection until that environment variable is removed.
- The field is part of the existing admin-only `connect.settings` infrastructure;
  no new model or access-control decision is introduced.
