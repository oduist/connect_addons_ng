# -*- coding: utf-8 -*-
"""Minimal, dependency-free Markdown -> HTML renderer.

Covers the subset of GitHub Flavored Markdown that is enough for the user
documentation: headings, paragraphs, lists (including nested ones), code
blocks, blockquotes, tables, horizontal rules and inline formatting (bold,
italic, code, links, images).

On top of that it understands the two MkDocs constructs the documentation in
this repository actually uses, so the Book renders the same pages the site
does: ``!!! note "Title"`` admonitions (pymdownx.details) and ``=== "Label"``
content tabs (pymdownx.tabbed). Both are block constructs whose body is
indented four spaces; the body is rendered recursively as Markdown.

Implemented "from scratch" so that the Book works in any Odoo image without
installing extra packages. All text is escaped, so no raw markup from the
source files ends up in the HTML.
"""
import re

from markupsafe import escape

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR_RE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_UL_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^(\s*)\d+[.)]\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+#.-]*)\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)+\|?\s*$")
#: ``!!! warning "Do not do this"`` -- the quoted title is optional.
_ADMONITION_RE = re.compile(r'^(\s*)!!!\s+([\w-]+)\s*(?:"(.*)")?\s*$')
#: ``=== "Twilio"`` -- one tab of a content-tab group.
_TAB_RE = re.compile(r'^(\s*)===\s+"(.*)"\s*$')

#: Admonition kinds we style. Anything else still renders, as a plain note.
_ADMONITION_KINDS = frozenset(
    {"note", "info", "tip", "warning", "danger", "example", "abstract", "success"}
)

#: Only these URL schemes may appear in rendered links/images. A URL that
#: carries any other explicit scheme (``javascript:``, ``data:``, ``vbscript:``…)
#: is neutralised to ``#`` so untrusted documentation cannot smuggle script.
#: Scheme-relative and relative URLs (no scheme) are allowed.
_URL_SCHEME_RE = re.compile(r"^\s*([a-z][a-z0-9+.\-]*):", re.I)
_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto"})

#: Cap on block recursion. Every construct whose body is Markdown of its own --
#: a list item, a blockquote, an admonition, a tab -- renders it by calling back
#: into :func:`md_to_html`, so one cap covers them all. It is a backstop against
#: pathological input overflowing the Python stack; real documentation never
#: nests anywhere near this deep.
_MAX_BLOCK_DEPTH = 12
#: Block constructs that end a list when they appear at or left of its indent.
#: Without this, a fenced block or heading following a list with no blank line
#: would be swallowed as a lazy continuation of the last item.
_BLOCK_STARTERS = (_FENCE_RE, _HEADING_RE, _HR_RE, _ADMONITION_RE, _TAB_RE)


def _safe_url(url):
    """Return ``url`` if its scheme is safe (or it has none), else ``"#"``."""
    match = _URL_SCHEME_RE.match(url)
    if match and match.group(1).lower() not in _SAFE_URL_SCHEMES:
        return "#"
    return url


def md_to_html(text, depth=0):
    """Convert a Markdown string into an HTML string.

    ``depth`` is the block-recursion level, passed by the constructs that render
    a nested body of their own; callers outside this module leave it alone.
    """
    if not text:
        return ""
    if depth > _MAX_BLOCK_DEPTH:
        # Too deeply nested to keep parsing; hand the text back escaped.
        return "<p>%s</p>" % escape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out = []
    para = []
    i, n = 0, len(lines)

    def flush_para():
        if para:
            joined = " ".join(line.strip() for line in para)
            out.append("<p>%s</p>" % _inline(joined))
            para.clear()

    while i < n:
        line = lines[i]

        fence = _FENCE_RE.match(line)
        if fence:
            flush_para()
            block, i = _consume_fence(lines, i, n, fence)
            out.append(block)
            continue

        if not line.strip():
            flush_para()
            i += 1
            continue

        admonition = _ADMONITION_RE.match(line)
        if admonition:
            flush_para()
            block, i = _consume_admonition(lines, i, n, admonition, depth)
            out.append(block)
            continue

        if _TAB_RE.match(line):
            flush_para()
            block, i = _consume_tabs(lines, i, n, depth)
            out.append(block)
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            flush_para()
            level = len(heading.group(1))
            raw = heading.group(2)
            out.append('<h%d id="%s">%s</h%d>' % (level, _slug(raw), _inline(raw), level))
            i += 1
            continue

        if _HR_RE.match(line):
            flush_para()
            out.append("<hr/>")
            i += 1
            continue

        if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            flush_para()
            block, i = _consume_table(lines, i, n)
            out.append(block)
            continue

        if line.lstrip().startswith(">"):
            flush_para()
            block, i = _consume_quote(lines, i, n, depth)
            out.append(block)
            continue

        if _UL_RE.match(line) or _OL_RE.match(line):
            flush_para()
            block, i = _consume_list(lines, i, n, depth)
            out.append(block)
            continue

        para.append(line)
        i += 1

    flush_para()
    return "\n".join(out)


def _consume_indented_body(lines, i, n, marker_indent):
    """Collect the indented body of a block construct, dedented.

    The body runs from ``i`` to the first non-blank line that is not indented
    deeper than ``marker_indent``. Trailing blank lines are dropped, so an
    empty body yields no markup at all.
    """
    body = []
    while i < n:
        line = lines[i]
        if not line.strip():
            body.append("")
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= marker_indent:
            break
        body.append(line[marker_indent + 4:] if indent >= marker_indent + 4 else line.lstrip())
        i += 1
    while body and not body[-1].strip():
        body.pop()
    return body, i


def _consume_admonition(lines, i, n, match, depth=0):
    """Render a ``!!! kind "Title"`` block and its indented body."""
    marker_indent = len(match.group(1))
    kind = match.group(2).lower()
    title = match.group(3)
    if kind not in _ADMONITION_KINDS:
        kind = "note"
    if title is None:
        title = kind.capitalize()
    body, i = _consume_indented_body(lines, i + 1, n, marker_indent)
    html = (
        '<div class="o_book_admonition o_book_admonition_%s">'
        '<p class="o_book_admonition_title">%s</p>%s</div>'
        % (kind, _inline(title), md_to_html("\n".join(body), depth + 1))
    )
    return html, i


def _consume_tabs(lines, i, n, depth=0):
    """Render a run of ``=== "Label"`` tabs as one labelled group.

    There is no JavaScript in the rendered documentation, so the tabs are laid
    out as consecutive labelled panels rather than as a switcher -- every
    variant stays readable, which is what matters in a manual.
    """
    panels = []
    while i < n:
        match = _TAB_RE.match(lines[i])
        if not match:
            break
        marker_indent = len(match.group(1))
        body, i = _consume_indented_body(lines, i + 1, n, marker_indent)
        panels.append(
            '<div class="o_book_tab">'
            '<p class="o_book_tab_label">%s</p>%s</div>'
            % (_inline(match.group(2)), md_to_html("\n".join(body), depth + 1))
        )
        # Blank lines between two tabs of the same group are not a separator.
        skip = i
        while skip < n and not lines[skip].strip():
            skip += 1
        if skip < n and _TAB_RE.match(lines[skip]):
            i = skip
    return '<div class="o_book_tabs">%s</div>' % "".join(panels), i


def _consume_fence(lines, i, n, fence):
    marker = fence.group(1)[0]
    lang = fence.group(2)
    closing = re.compile(r"^\s*%s{3,}\s*$" % re.escape(marker))
    body = []
    i += 1
    while i < n and not closing.match(lines[i]):
        body.append(lines[i])
        i += 1
    i += 1  # skip the closing fence
    cls = ' class="language-%s"' % lang if lang else ""
    code = _render_diff(body) if lang == "diff" else str(escape("\n".join(body)))
    return "<pre><code%s>%s</code></pre>" % (cls, code), i


def _render_diff(body):
    """Render a ``diff`` fenced block: colour added/removed lines.

    Added lines (``+``) and removed lines (``-``) are wrapped in spans so the
    documentation-change archive shows green/red diffs. Everything is escaped.
    """
    rendered = []
    for line in body:
        cell = str(escape(line))
        if line[:1] == "+":
            rendered.append('<span class="o_diff_add">%s</span>' % cell)
        elif line[:1] == "-":
            rendered.append('<span class="o_diff_del">%s</span>' % cell)
        else:
            rendered.append(cell)
    return "\n".join(rendered)


def _consume_quote(lines, i, n, depth=0):
    quoted = []
    while i < n and lines[i].lstrip().startswith(">"):
        quoted.append(re.sub(r"^\s*>\s?", "", lines[i]))
        i += 1
    return "<blockquote>%s</blockquote>" % md_to_html("\n".join(quoted), depth + 1), i


def _consume_table(lines, i, n):
    header = _split_row(lines[i])
    i += 2  # header row + separator row
    rows = []
    while i < n and lines[i].strip() and "|" in lines[i]:
        rows.append(_split_row(lines[i]))
        i += 1
    html = ["<table><thead><tr>"]
    html += ["<th>%s</th>" % _inline(cell) for cell in header]
    html.append("</tr></thead><tbody>")
    for row in rows:
        html.append("<tr>")
        html += ["<td>%s</td>" % _inline(cell) for cell in row]
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html), i


def _split_row(row):
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def _consume_list(lines, i, n, depth=0):
    """Consume one list and render it, items and all.

    An item owns everything that belongs to it: its own text, its wrapped
    continuation lines, a nested list, an indented code block, a further
    paragraph. Those lines are collected verbatim (dedented by one level) and
    rendered by calling back into :func:`md_to_html`, so an item can hold any
    block construct without this function having to know about it.

    Blank lines do **not** end a list. A blank line followed by another marker,
    or by indented content, is an item separator inside the same list -- which
    is how nearly every list in the documentation is written, and what keeps an
    ordered list numbering 1, 2, 3 instead of restarting at 1 on every item.
    """
    base_indent = _indent_of(lines[i])
    ordered = bool(_OL_RE.match(lines[i]))
    items = []
    while i < n:
        line = lines[i]

        if not line.strip():
            # A blank line belongs to the list only if the list continues after
            # it; otherwise it is the end of the list.
            skip = i
            while skip < n and not lines[skip].strip():
                skip += 1
            if skip >= n or not _continues_list(lines[skip], base_indent):
                break
            if items:
                items[-1].append("")
            i = skip
            continue

        indent = _indent_of(line)
        marker = _UL_RE.match(line) or _OL_RE.match(line)

        if marker and indent <= base_indent:
            if bool(_OL_RE.match(line)) != ordered:
                # The kind flips: this is a new list, not another item.
                break
            items.append([marker.group(2)])
            i += 1
            continue

        if indent > base_indent:
            # Content belonging to the current item: dedent one level and keep
            # it verbatim for the recursive render.
            if not items:
                break
            items[-1].append(
                line[base_indent + 4:] if indent >= base_indent + 4 else line.lstrip()
            )
            i += 1
            continue

        # Unindented and not a marker. A plain paragraph line is a lazy
        # continuation of the last item; any other block construct ends the list.
        if not items or any(rx.match(line) for rx in _BLOCK_STARTERS):
            break
        items[-1].append(line.strip())
        i += 1

    if not items:
        return "", i
    tag = "ol" if ordered else "ul"
    rendered = "".join(
        "<li>%s</li>" % _render_item(item, depth) for item in items
    )
    return "<%s>%s</%s>" % (tag, rendered, tag), i


def _indent_of(line):
    """Indentation width of ``line``, counting a tab as four spaces."""
    stripped = line.lstrip(" \t")
    return len(line[: len(line) - len(stripped)].replace("\t", "    "))


def _continues_list(line, base_indent):
    """Does ``line``, the first non-blank after a gap, continue the list?"""
    if _UL_RE.match(line) or _OL_RE.match(line):
        return _indent_of(line) >= base_indent
    return _indent_of(line) > base_indent


def _render_item(item_lines, depth):
    """Render one list item's collected lines.

    A single-line item stays "tight" -- inline markup only, no wrapping
    paragraph -- which is what a plain bullet list should look like. An item
    carrying more than that is rendered as full Markdown.
    """
    content = [line for line in item_lines if line.strip()]
    if len(content) == 1:
        return _inline(content[0])
    return md_to_html("\n".join(item_lines), depth + 1)


def _inline(text):
    """Inline formatting. Escapes the text and inserts safe HTML."""
    codes = []

    def _stash(match):
        codes.append(str(escape(match.group(1))))
        return "\x00%d\x00" % (len(codes) - 1)

    # First stash the inline code so its contents are not formatted.
    text = re.sub(r"`([^`]+)`", _stash, text)
    text = str(escape(text))
    # URLs are already HTML-escaped here; still validate their scheme so a
    # javascript:/data: link cannot execute when the HTML is injected via markup().
    text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda m: '<img src="%s" alt="%s"/>' % (_safe_url(m.group(2)), m.group(1)),
        text,
    )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: '<a href="%s" target="_blank" rel="noreferrer noopener">%s</a>'
        % (_safe_url(m.group(2)), m.group(1)),
        text,
    )
    # Handle bold before italic; leave underscores alone so we don't break
    # technical identifiers like res_partner or connect_book.
    text = re.sub(r"\*\*([^*]+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: "<code>%s</code>" % codes[int(m.group(1))], text)
    return text


def _slug(text):
    s = re.sub(r"<[^>]+>", "", text)
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_]+", "-", s)
