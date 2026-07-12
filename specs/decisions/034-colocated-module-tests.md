# ADR-034: Colocated Module Tests

## Status
Accepted

## Context
The former private test repository caused recurring gitlink conflicts and made
test delivery fragile in feature branches and Oduflow environments. Tests should
travel with the code they verify and be available through the normal repository
checkout.

## Decision
Store Odoo tests directly inside each owning module's `tests/` package.

- Test files live in `<module>/tests/test_*.py`.
- Shared test helpers live beside them, for example `<module>/tests/common.py`.
- Each populated `tests/__init__.py` explicitly imports every `test_*.py` file
  so Odoo's standard test discovery sees the tests.
- The repository does not use a test submodule, gitlink, symlinked test
  directory, or dynamic import loader.

## Consequences
- Implementation and regression tests are reviewed, merged, and backported
  together.
- Oduflow receives tests through the same git workflow as module code.
- There is no separate test-repository branch policy or gitlink bump step.
