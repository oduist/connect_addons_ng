# ADR-050: Use the Oduflow MCP server as the instruction source

**Status:** Accepted
**Date:** 2026-08-16

## Context

The repository contained a local `.claude/skills/oduflow` skill with a copy of
the Oduflow workflow and tool reference. Oduflow MCP also provides instructions
for its current server capabilities. Maintaining both copies allows the local
skill to drift from the deployed MCP server and can make agents follow obsolete
tool contracts.

Repository-specific Oduflow policies in `AGENTS.md` remain useful because they
describe this project's deployment order, test modules, secrets handling, and
verification requirements rather than the generic MCP API.

## Decision

- Remove the local `.claude/skills/oduflow` skill and its copied tool reference.
- Treat instructions supplied by the Oduflow MCP server as the source of truth
  for available tools and their generic usage.
- Keep repository-specific Oduflow workflow and safety rules in `AGENTS.md`.
- Keep `.claude/skills/oduflow-log-usecase` because it implements a separate,
  repository-specific logging workflow and does not replace MCP instructions.

## Consequences

- Oduflow tool guidance updates with the MCP server instead of requiring a
  synchronized repository change.
- Agents no longer receive conflicting generic instructions from a stale local
  skill.
- Project-specific deployment and verification constraints remain versioned
  with the repository.
