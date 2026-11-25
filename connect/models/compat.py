# -*- coding: utf-8 -*-
"""Thin cross-series compatibility helpers.

Python files are byte-identical across series branches (see AGENTS.md,
Version Compatibility). Behavior that cannot be expressed uniformly
branches here on release.version_info instead of forking the caller.
"""
from odoo import release


def env_translate(env, source, **kwargs):
    """Translate a code literal in the language of ``env``.

    ``env._`` only exists on Odoo >= 17; earlier series fall back to the
    classic frame-inspecting ``_``, which resolves the language from the
    ``context`` local below. Placeholders are interpolated after
    translation so both arms behave the same.
    """
    if release.version_info[0] >= 17:
        translated = env._(source)
    else:
        # Imported lazily: this arm never runs on the new series.
        from odoo.tools.translate import _
        context = env.context  # noqa: F841 -- read by _'s frame inspection
        translated = _(source)
    if not kwargs:
        return translated
    try:
        return translated % kwargs
    except (KeyError, TypeError, ValueError):
        # A malformed translation must not break the caller; fall back to
        # the untranslated source, as odoo's own formatting path does.
        return source % kwargs
