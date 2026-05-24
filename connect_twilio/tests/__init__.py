"""Conditional test loader.

When the private tests_suite submodule is initialised, dynamically loads
test_*.py modules from tests_suite/connect_twilio/tests/ and exposes them
as submodules so Odoo's test discovery (inspect.getmembers + ismodule)
picks them up.

When tests_suite is absent (external uv consumers, fresh clones without
the private submodule), this file is a no-op and the addon installs
cleanly with no tests.

MUST NEVER raise: odoo.tests.loader._get_tests_modules does not wrap
the import call, so any exception here aborts test collection for the
whole addon.
"""
import importlib.util
import os
import sys

_SUITE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..",
                 "tests_suite", "connect_twilio", "tests")
)

if os.path.isdir(_SUITE):
    for _fn in sorted(os.listdir(_SUITE)):
        if not (_fn.startswith("test_") and _fn.endswith(".py")):
            continue
        _name = _fn[:-3]
        _full = f"{__name__}.{_name}"
        try:
            _spec = importlib.util.spec_from_file_location(
                _full, os.path.join(_SUITE, _fn))
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules[_full] = _mod
            _spec.loader.exec_module(_mod)
            globals()[_name] = _mod
        except Exception:
            pass
