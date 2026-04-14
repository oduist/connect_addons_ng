# ADR-011: Gated Test Suite Architecture

## Status
Accepted

## Context
We are transitioning from selling support to selling infrastructure for AI customization. As AI agents increasingly write code, the value shifts from writing functions to verifying them. We need a business model that:

- Encourages customers to use AI agents for module customization
- Provides a paid "safety net" (test suite) that validates customizations
- Keeps business logic open while protecting verification infrastructure

## Decision
Implement an **Agent-Ready Module** architecture with a **Gated Test Suite**:

### Structure
- **Main repo** (`connect_addons_ng`): Contains only business logic modules
- **Private submodule** (`tests_suite/`): Contains all unit and integration tests in a separate private repository (`oduist/connect_addons_tests`)
- **Symlinks**: Each module's `tests/` directory is a relative symlink to the corresponding folder in the submodule (e.g., `connect/tests → ../tests_suite/connect/tests`)

### Operating Modes
1. **Unprotected Mode**: Customer has no access to the private submodule. Symlinks are broken, `tests/` is empty. Code can be modified but not verified.
2. **Safe Mode**: Customer purchases access to `tests_suite`. Symlinks resolve. AI agents can run tests after every customization, providing industrial-grade stability guarantees.

### Agent-First Documentation
Each module ships with deep AI context (`CLAUDE.md` / `AGENTS.md`) that instructs customer AI agents how to properly extend and customize modules without breaking core logic.

## Alternatives Considered

1. **Tests inline in modules**: No separation — gives away verification for free, no monetization path.
2. **Separate test repo without symlinks**: Requires custom test discovery config; breaks standard Odoo test runner expectations.
3. **Encrypted/obfuscated tests**: Adds complexity, breaks IDE support, hostile to developers.

## Consequences

- Customers get full source code for customization — AI agents work at full capacity
- Test suite becomes a paid product providing verification infrastructure
- Broken symlinks in unprotected mode are expected, not errors
- `CLAUDE.md` must document both modes so AI agents behave correctly
