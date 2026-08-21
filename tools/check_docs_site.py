#!/usr/bin/env python3
"""Structural assertions for the built documentation site.

Run after `mkdocs build`. The docs site has no unit tests: these checks are the
regression net for the theme's templates — every invariant a task establishes
gets an assertion here, so a later task cannot silently break it.

Usage: python3 tools/check_docs_site.py [site_dir]
"""

import pathlib
import re
import sys

SITE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site")

# One representative page per template path through the site.
HOME = SITE / "index.html"
MODULE_PAGE = SITE / "Twilio" / "configuration" / "index.html"
CHANGELOG = SITE / "changelog" / "index.html"
# Carries both a code block and a tabbed set; the Twilio page has neither.
CODE_PAGE = SITE / "Core" / "admin" / "installation" / "index.html"
NOT_FOUND = SITE / "404.html"

failures = []


def check(name):
    """Register a check. Each returns None on success or a failure message."""

    def register(fn):
        fn.check_name = name
        CHECKS.append(fn)
        return fn

    return register


CHECKS = []


def read(path):
    if not path.exists():
        raise AssertionError(f"{path} was not built")
    return path.read_text(encoding="utf-8")


@check("every representative page was built")
def _pages_exist():
    for path in (HOME, MODULE_PAGE, CHANGELOG, NOT_FOUND):
        if not path.exists():
            return f"{path} is missing"


@check("pages link the compiled stylesheet")
def _stylesheet_linked():
    for path in (HOME, MODULE_PAGE, NOT_FOUND):
        html = read(path)
        if "assets/app.css" not in html:
            return f"{path} does not link assets/app.css"


@check("the search index was emitted")
def _search_index():
    if not (SITE / "search" / "search_index.json").exists():
        return "search/search_index.json is missing"


@check("pages carry the theme skeleton")
def _skeleton():
    html = read(MODULE_PAGE)
    for marker in ('data-theme=', 'class="docs-content', "assets/theme.js"):
        if marker not in html:
            return f"{marker!r} missing from {MODULE_PAGE}"


@check("no Material markup survives")
def _no_material():
    for path in (HOME, MODULE_PAGE, CHANGELOG):
        html = read(path)
        if "md-header" in html or "data-md-color-scheme" in html:
            return f"{path} still contains Material markup"


@check("the sidebar is scoped to the current module")
def _sidebar_scope():
    html = read(MODULE_PAGE)
    if 'class="docs-nav"' not in html:
        return "no sidebar rendered on a module page"
    # The Twilio page must not advertise other modules in its sidebar.
    sidebar = html.split('class="docs-nav"', 1)[1].split("</nav>", 1)[0]
    for stranger in ("FreeSWITCH", "LiveKit", "Telnyx"):
        if stranger in sidebar:
            return f"sidebar leaks {stranger} on a Twilio page"


@check("root pages hide the sidebar")
def _root_pages_have_no_sidebar():
    if 'class="docs-nav"' in read(HOME):
        return "the home page renders a sidebar despite hide: navigation"


@check("breadcrumbs walk back to home")
def _breadcrumbs():
    html = read(MODULE_PAGE)
    if 'class="docs-crumbs"' not in html:
        return "no breadcrumb trail on a module page"
    crumbs = html.split('class="docs-crumbs"', 1)[1].split("</nav>", 1)[0]
    if "Twilio" not in crumbs or ">Home<" not in crumbs:
        return "breadcrumb trail does not run Home -> Twilio"


@check("the page TOC is rendered")
def _toc():
    if 'class="docs-toc"' not in read(MODULE_PAGE):
        return "no table of contents on a module page"


@check("admonitions and tables are wrapped for styling")
def _content_components():
    html = read(MODULE_PAGE)
    if "admonition" not in html:
        return "expected an admonition on the Twilio configuration page"
    # Table wrapping happens client-side (js/copy.js wrapTables(), run from
    # theme.js), so static HTML never carries docs-table-wrap. Check that the
    # CSS the wrapper depends on actually shipped instead.
    if "docs-table-wrap" not in (SITE / "assets" / "app.css").read_text():
        return "the table wrapper class is not in the compiled stylesheet"


@check("code blocks carry Pygments classes")
def _code_highlighting():
    html = read(CODE_PAGE)
    if 'class="highlight"' not in html:
        return "no highlighted code block found"


@check("the search dialog and engine ship with the site")
def _search_ui():
    html = read(MODULE_PAGE)
    if "data-search" not in html:
        return "no search dialog in the page"
    if not (SITE / "assets" / "vendor" / "lunr.min.js").exists():
        return "lunr.min.js was not copied into the site"


@check("the home page keeps its component class names")
def _home_components():
    html = read(HOME)
    for cls in ("hero-art", "mod-grid", "mod-tile", "docs-button"):
        if cls not in html:
            return f"{cls} missing from the home page"
    if "md-button" in html:
        return "md-button still present on the home page"


def main():
    for fn in CHECKS:
        try:
            problem = fn()
        except AssertionError as exc:
            problem = str(exc)
        if problem:
            failures.append(f"{fn.check_name}: {problem}")

    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        print(f"\n{len(failures)} of {len(CHECKS)} checks failed")
        return 1
    print(f"OK: {len(CHECKS)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
