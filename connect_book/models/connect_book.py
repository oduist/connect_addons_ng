# -*- coding: utf-8 -*-
import logging
import os
import re

from odoo import api, models
from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path

from .markdown import md_to_html

_logger = logging.getLogger(__name__)

#: Folder inside a module that holds its documentation pages. This is the very
#: same folder the documentation site is built from -- see the root
#: ``mkdocs.yml``, which aggregates every module's ``docs`` through
#: mkdocs-monorepo-plugin. The Book is a second reader of one source, never a
#: second copy of it.
DOCS_DIRNAME = "docs"
#: Per-module MkDocs config next to that folder. It carries the module's
#: display name (``site_name``) and the page order and titles (``nav``), so the
#: Book presents pages exactly as the site does.
MKDOCS_FILENAME = "mkdocs.yml"
#: Folder inside ``docs`` holding translated mirrors: ``docs/i18n/<lang>/<page>``.
I18N_DIRNAME = "i18n"
#: Leading provenance marker a translated file carries; stripped before render.
I18N_MARKER_RE = re.compile(r"\A<!--\s*i18n\b[^>]*-->[ \t]*\r?\n?")
#: MkDocs page metadata (``---`` … ``---``) is for the site, not for the Book.
FRONT_MATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*\r?\n?", re.S)
#: Prefix of the modules included in the Book (covers ``connect`` itself
#: and every ``connect_*`` add-on).
MODULE_PREFIX = "connect"
#: Group required to read the User Guide. ``connect.group_admin`` implies it.
USER_GROUP = "connect.group_user"
#: Group required to read the Admin Guide -- admin guides describe privileged
#: settings and tasks, and this is the group that may open them in the UI.
ADMIN_GROUP = "connect.group_admin"
#: A documentation-language code is a short lowercase tag (optionally ``@variant``).
#: Anything else is rejected so a crafted ``lang`` cannot escape the docs folder
#: when it is joined into a filesystem path.
LANG_CODE_RE = re.compile(r"^[a-z]{2,3}(@[a-z0-9]+)?$")
#: Skip absurdly large docs so a single file cannot dominate render time.
MAX_DOC_BYTES = 1024 * 1024

#: The two audiences, and the two books.
AUDIENCE_USER = "user"
AUDIENCE_ADMIN = "admin"
#: A ``nav`` section whose title is one of these declares its pages' audience
#: explicitly; this wins over everything else.
SECTION_AUDIENCE = {
    "admin guide": AUDIENCE_ADMIN,
    "user guide": AUDIENCE_USER,
}
#: Otherwise the first path segment decides: ``docs/admin/…`` / ``docs/user/…``.
PREFIX_AUDIENCE = {
    "admin": AUDIENCE_ADMIN,
    "user": AUDIENCE_USER,
}
#: A page that declares neither is treated as administrator documentation. That
#: is the safe default (it never widens who can read a page) and it is also the
#: truthful one: the flat pages in this repository are setup and configuration
#: guides written for an administrator.
DEFAULT_AUDIENCE = AUDIENCE_ADMIN

_SITE_NAME_RE = re.compile(r"^site_name:\s*(.+?)\s*$")
_NAV_START_RE = re.compile(r"^nav:\s*$")
#: ``- Messages (SMS & WhatsApp): user/messages.md`` -- the title is greedy so a
#: colon inside it binds to the title, not to the path.
_NAV_PAGE_RE = re.compile(r"^(\s*)-\s+(.*):\s*(\S+\.md)\s*$")
#: ``- Admin Guide:`` -- a section that groups the entries indented below it.
_NAV_SECTION_RE = re.compile(r"^(\s*)-\s+(.*):\s*$")
#: A nav path must stay inside the docs folder: plain relative segments only.
_NAV_PATH_RE = re.compile(r"^[\w-]+(/[\w-]+)*\.md$")
#: A rendered link to another Markdown page, as emitted by :mod:`.markdown`.
_MD_LINK_RE = re.compile(
    r'<a href="(?P<href>[^"]*\.md(?:#[^"]*)?)" target="_blank" rel="noreferrer noopener">'
)

#: Rendered-Markdown cache keyed by ``(filepath, strip_marker)`` -> ``(mtime, html)``.
#: Per-worker and bounded by the number of doc files across installed modules;
#: invalidated automatically when a file's mtime changes (i.e. on redeploy).
_RENDER_CACHE = {}
#: Parsed-``mkdocs.yml`` cache keyed by filepath -> ``(mtime, site_name, entries)``.
_NAV_CACHE = {}


def _unquote(value):
    """Strip one layer of matching quotes off a YAML scalar."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


class ConnectBook(models.AbstractModel):
    """Documentation collector for the installed ``connect*`` modules.

    The model stores nothing (no table): it reads the modules from disk and
    assembles their documentation into books. Two audiences, two books: the
    **User Guide** (for everyone with a Connect role) and the **Admin Guide**
    (settings and privileged tasks, gated behind the Connect admin group).

    Pages come from each module's own ``docs`` folder -- the same files the
    public documentation site is built from -- and are titled and ordered by
    that module's ``mkdocs.yml`` ``nav``. Which book a page lands in is decided
    by :meth:`_page_audience`.

    Both books are served in the reader's documentation language: a translated
    mirror under ``docs/i18n/<lang>/`` is preferred, falling back to the source
    file.
    """

    _name = "connect.book"
    _description = "Connect Book"

    @api.model
    def get_book(self):
        """Assemble the User Guide from every installed ``connect*`` module.

        :raise AccessError: when the caller has no Connect role.
        :return: ``{"modules": [{"id", "title", "pages": [...]}, ...]}`` --
            see :meth:`_collect_modules` for the page shape.
        """
        if not self.env.user.has_group(USER_GROUP):
            raise AccessError(
                self.env._("A Connect role is required to read the User Guide.")
            )
        return {"modules": self._collect_modules(AUDIENCE_USER, self._doc_lang())}

    @api.model
    def get_admin_book(self):
        """Assemble the Admin Guide. Connect administrators only.

        Same shape as :meth:`get_book`, but it collects the pages classified as
        administrator documentation, because those describe privileged settings
        and tasks.

        :raise AccessError: when the caller is not a Connect administrator.
        :return: ``{"modules": [...]}``.
        """
        if not self.env.user.has_group(ADMIN_GROUP):
            raise AccessError(
                self.env._(
                    "Connect administrator access is required to read the Admin Guide."
                )
            )
        return {"modules": self._collect_modules(AUDIENCE_ADMIN, self._doc_lang())}

    def _doc_lang(self):
        """Short documentation-language code for the current request.

        Derived from the context/user language (``en_US`` -> ``en``).
        Translations live under ``docs/i18n/<lang>/``; a missing one falls back
        to the source file -- the read path is purely "translated-if-present,
        else source".
        """
        lang = (self.env.context.get("lang") or self.env.user.lang or "en").split("_")[0]
        # Reject anything that is not a plain language tag so the value is safe
        # to join into a filesystem path (no ``/``, ``.``, ``..`` traversal).
        if not LANG_CODE_RE.match(lang):
            return "en"
        return lang

    def _collect_modules(self, audience, lang):
        """Collect the pages of ``audience`` from every installed module.

        :param audience: :data:`AUDIENCE_USER` or :data:`AUDIENCE_ADMIN`.
        :param lang: the short documentation-language code to prefer.
        :return: ``[{"id", "title", "pages": [{"id", "title", "html"}, ...]},
            ...]`` -- one entry per module that ships at least one readable
            page for this audience, ordered by module name, pages in ``nav``
            order.
        """
        modules = self.env["ir.module.module"].sudo().search(
            [
                ("state", "=", "installed"),
                ("name", "=like", MODULE_PREFIX + "%"),
            ],
            order="name",
        )
        collected = []
        for module in modules:
            module_path = get_module_path(module.name)
            if not module_path:
                continue
            site_name, entries = self._read_nav(module_path)
            pages = []
            for title, relpath, page_audience in entries:
                if page_audience != audience:
                    continue
                html = self._read_module_doc(module_path, relpath, lang)
                if html is None:
                    continue
                pages.append(
                    {
                        "id": "%s/%s" % (module.name, relpath),
                        "title": title,
                        "html": self._rewrite_internal_links(
                            html, module.name, relpath
                        ),
                    }
                )
            if not pages:
                continue
            collected.append(
                {
                    "id": module.name,
                    "title": site_name or module.shortdesc or module.name,
                    "pages": pages,
                }
            )
        return collected

    def _read_nav(self, module_path):
        """Parse a module's ``mkdocs.yml``. Returns ``(site_name, entries)``.

        ``entries`` is ``[(title, relpath, audience), ...]`` in ``nav`` order.
        A module without a ``mkdocs.yml`` simply has no pages.

        The file is read with a small purpose-built parser rather than a YAML
        library: these nav blocks are a fixed, two-level shape, and the Book
        must work in any Odoo image without an extra dependency -- the same
        reason :mod:`.markdown` renders Markdown by hand.
        """
        filepath = os.path.join(module_path, MKDOCS_FILENAME)
        try:
            stat = os.stat(filepath)
        except OSError:
            return None, []
        cached = _NAV_CACHE.get(filepath)
        if cached is not None and cached[0] == stat.st_mtime:
            return cached[1], cached[2]
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                lines = handle.read().splitlines()
        except (OSError, UnicodeDecodeError):
            _logger.warning("connect_book: failed to read %s", filepath)
            return None, []
        site_name, entries = self._parse_nav(lines)
        _NAV_CACHE[filepath] = (stat.st_mtime, site_name, entries)
        return site_name, entries

    def _parse_nav(self, lines):
        """Pull ``site_name`` and the ``nav`` entries out of mkdocs.yml lines."""
        site_name = None
        entries = []
        in_nav = False
        base_indent = None
        section = None
        for line in lines:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not in_nav:
                name = _SITE_NAME_RE.match(line)
                if name:
                    site_name = _unquote(name.group(1))
                elif _NAV_START_RE.match(line):
                    in_nav = True
                continue
            indent = len(line) - len(line.lstrip())
            if indent == 0:
                # A new top-level key: the nav block is over.
                break
            if base_indent is None:
                base_indent = indent
            if indent <= base_indent:
                # Back at the top of the nav: any section we were in has ended.
                section = None
            page = _NAV_PAGE_RE.match(line)
            if page:
                relpath = _unquote(page.group(3))
                if _NAV_PATH_RE.match(relpath):
                    entries.append(
                        (
                            _unquote(page.group(2)),
                            relpath,
                            self._page_audience(relpath, section),
                        )
                    )
                continue
            heading = _NAV_SECTION_RE.match(line)
            if heading:
                section = _unquote(heading.group(2)).strip().lower()
        return site_name, entries

    def _page_audience(self, relpath, section):
        """Decide which book a page belongs to.

        An explicit ``nav`` section (``Admin Guide`` / ``User Guide``) wins; a
        path prefix (``admin/`` / ``user/``) is the fallback; anything else is
        :data:`DEFAULT_AUDIENCE`.
        """
        if section in SECTION_AUDIENCE:
            return SECTION_AUDIENCE[section]
        head = relpath.split("/")[0] if "/" in relpath else ""
        return PREFIX_AUDIENCE.get(head, DEFAULT_AUDIENCE)

    def _read_module_doc(self, module_path, relpath, lang):
        """Read and render ``docs/<relpath>`` of a module in ``lang`` (or None).

        Looks for a translation under ``docs/i18n/<lang>/<relpath>`` first and
        falls back to the source page.
        """
        candidates = [
            os.path.join(module_path, DOCS_DIRNAME, I18N_DIRNAME, lang, *relpath.split("/")),
            os.path.join(module_path, DOCS_DIRNAME, *relpath.split("/")),
        ]
        for filepath in candidates:
            if not os.path.isfile(filepath):
                continue
            return self._render_doc_html(filepath)
        return None

    def _render_doc_html(self, filepath):
        """Read, strip the metadata headers, and render a Markdown file.

        Cached by ``(filepath, mtime)`` so repeat Book opens don't re-read and
        re-parse unchanged files. Oversized files are skipped, and a rendering
        failure isolates to this one file (returns ``None``) rather than
        breaking the whole book.
        """
        try:
            stat = os.stat(filepath)
        except OSError:
            _logger.warning("connect_book: failed to stat %s", filepath)
            return None
        if stat.st_size > MAX_DOC_BYTES:
            _logger.warning(
                "connect_book: skipping oversized doc %s (%d bytes)",
                filepath,
                stat.st_size,
            )
            return None
        cached = _RENDER_CACHE.get(filepath)
        if cached is not None and cached[0] == stat.st_mtime:
            return cached[1]
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                raw = handle.read()
        except (OSError, UnicodeDecodeError):
            _logger.warning("connect_book: failed to read %s", filepath)
            return None
        raw = I18N_MARKER_RE.sub("", raw, count=1)
        raw = FRONT_MATTER_RE.sub("", raw, count=1)
        try:
            html = md_to_html(raw)
        except Exception:  # noqa: BLE001 — one bad file must not sink the book
            _logger.exception("connect_book: failed to render %s", filepath)
            return None
        _RENDER_CACHE[filepath] = (stat.st_mtime, html)
        return html

    def _rewrite_internal_links(self, html, module_name, relpath):
        """Turn links between Markdown pages into in-Book page jumps.

        The documentation cross-links pages by relative file name
        (``[Security](security.md)``), which the site resolves and a browser
        inside Odoo cannot. Each such link is rewritten to carry the target's
        page id in ``data-book-page`` so the client action can switch to it;
        links that leave the module's docs folder are left inert.
        """
        base = os.path.dirname(relpath)

        def replace(match):
            href = match.group("href").split("#")[0]
            target = os.path.normpath(os.path.join(base, href)).replace(os.sep, "/")
            if not _NAV_PATH_RE.match(target):
                return '<a href="#">'
            return '<a href="#" data-book-page="%s/%s">' % (module_name, target)

        return _MD_LINK_RE.sub(replace, html)
