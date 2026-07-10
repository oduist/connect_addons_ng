"""Conditional loader for private connect_pipecat tests."""
import importlib.util
import os
import sys

_SUITE = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..',
    'tests_suite', 'connect_pipecat', 'tests',
))


def _load(filename):
    name = filename[:-3]
    full_name = '{}.{}'.format(__name__, name)
    try:
        spec = importlib.util.spec_from_file_location(
            full_name, os.path.join(_SUITE, filename),
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)
        globals()[name] = module
    except Exception:
        pass


if os.path.isdir(_SUITE):
    files = sorted(os.listdir(_SUITE))
    for filename in files:
        if (filename.endswith('.py') and not filename.startswith('test_')
                and filename != '__init__.py'):
            _load(filename)
    for filename in files:
        if filename.startswith('test_') and filename.endswith('.py'):
            _load(filename)
