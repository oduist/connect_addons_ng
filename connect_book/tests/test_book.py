# -*- coding: utf-8 -*-
import os
import tempfile
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.connect_book.models.connect_book import (
    AUDIENCE_ADMIN,
    AUDIENCE_USER,
    MAX_DOC_BYTES,
)


@tagged("post_install", "-at_install", "connect_book")
class TestConnectBook(TransactionCase):
    """The read path is exercised against a fake module directory on disk."""

    def setUp(self):
        super().setUp()
        self.book = self.env["connect.book"]
        # TransactionCase runs as the technical superuser (uid=1), a different
        # record from base.user_admin -- the one connect/security/groups.xml
        # actually grants connect.group_admin to. Grant it the Connect admin
        # role so the tests that call get_book()/get_admin_book() directly on
        # self.book behave like a real Connect administrator.
        self.env.user.write({
            "group_ids": [(4, self.env.ref("connect.group_admin").id)]
        })
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.module_path = self.tmp.name

    def _write_doc(self, relpath, content):
        """Write a page into the fake module's docs folder."""
        path = os.path.join(self.module_path, "docs", *relpath.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _write_change(self, filename, content):
        """Write a day file into the fake module's change archive."""
        path = os.path.join(self.module_path, "docs", "changes", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def _write_mkdocs(self, content):
        with open(
            os.path.join(self.module_path, "mkdocs.yml"), "w", encoding="utf-8"
        ) as handle:
            handle.write(content)

    def _patch_path(self):
        """Point get_module_path() at the temporary module directory."""
        return patch(
            "odoo.addons.connect_book.models.connect_book.get_module_path",
            return_value=self.module_path,
        )

    # -- language ----------------------------------------------------------

    def test_doc_lang_normalises_locale(self):
        self.assertEqual(self.book.with_context(lang="en_US")._doc_lang(), "en")

    def test_doc_lang_rejects_path_traversal(self):
        self.assertEqual(self.book.with_context(lang="../../etc")._doc_lang(), "en")

    # -- nav parsing -------------------------------------------------------

    def test_parse_nav_reads_site_name_and_flat_pages(self):
        site_name, entries = self.book._parse_nav(
            [
                "# a comment",
                "site_name: Twilio",
                "nav:",
                "  - Overview: index.md",
                "  - Messages (SMS & WhatsApp): messaging.md",
            ]
        )
        self.assertEqual(site_name, "Twilio")
        self.assertEqual(
            entries,
            [
                ("Overview", "index.md", AUDIENCE_ADMIN),
                ("Messages (SMS & WhatsApp)", "messaging.md", AUDIENCE_ADMIN),
            ],
        )

    def test_parse_nav_sections_decide_the_audience(self):
        _site, entries = self.book._parse_nav(
            [
                "site_name: Core",
                "nav:",
                "  - Admin Guide:",
                "      - Installation: install.md",
                "  - User Guide:",
                "      - Getting Started: start.md",
            ]
        )
        self.assertEqual(
            entries,
            [
                ("Installation", "install.md", AUDIENCE_ADMIN),
                ("Getting Started", "start.md", AUDIENCE_USER),
            ],
        )

    def test_parse_nav_falls_back_to_the_path_prefix(self):
        _site, entries = self.book._parse_nav(
            [
                "site_name: FreeSWITCH",
                "nav:",
                "  - Call Parking: user/parking.md",
                "  - SIP Firewall: admin/firewall.md",
                "  - fs_cli Reference: fs_cli.md",
            ]
        )
        self.assertEqual(
            [audience for _t, _p, audience in entries],
            [AUDIENCE_USER, AUDIENCE_ADMIN, AUDIENCE_ADMIN],
        )

    def test_parse_nav_stops_at_the_next_top_level_key(self):
        _site, entries = self.book._parse_nav(
            [
                "nav:",
                "  - Overview: index.md",
                "plugins:",
                "  - search",
            ]
        )
        self.assertEqual(entries, [("Overview", "index.md", AUDIENCE_ADMIN)])

    def test_parse_nav_rejects_a_path_that_escapes_the_docs_folder(self):
        _site, entries = self.book._parse_nav(
            [
                "nav:",
                "  - Escape: ../../secrets.md",
                "  - Fine: index.md",
            ]
        )
        self.assertEqual(entries, [("Fine", "index.md", AUDIENCE_ADMIN)])

    # -- reading pages -----------------------------------------------------

    def test_read_module_doc_prefers_translation(self):
        self._write_doc("index.md", "# Source\n")
        self._write_doc(
            "i18n/fr/index.md",
            "<!-- i18n source=index.md sha=abc lang=fr -->\n# Source FR\n",
        )
        html = self.book._read_module_doc(self.module_path, "index.md", "fr")
        self.assertIn("Source FR", html)
        self.assertNotIn("i18n source=", html)

    def test_read_module_doc_falls_back_to_source(self):
        self._write_doc("index.md", "# Source\n")
        html = self.book._read_module_doc(self.module_path, "index.md", "de")
        self.assertIn("Source", html)

    def test_read_module_doc_missing_returns_none(self):
        self.assertIsNone(
            self.book._read_module_doc(self.module_path, "nope.md", "en")
        )

    def test_read_module_doc_strips_front_matter(self):
        self._write_doc("index.md", "---\ntitle: Home\n---\n\n# Real\n")
        html = self.book._read_module_doc(self.module_path, "index.md", "en")
        self.assertNotIn("title: Home", html)
        self.assertIn("Real", html)

    def test_read_module_doc_skips_oversized_file(self):
        self._write_doc("index.md", "x" * (MAX_DOC_BYTES + 1))
        self.assertIsNone(
            self.book._read_module_doc(self.module_path, "index.md", "en")
        )

    def test_render_doc_html_returns_none_on_render_failure(self):
        self._write_doc("index.md", "# Guide\n")
        filepath = os.path.join(self.module_path, "docs", "index.md")
        with patch(
            "odoo.addons.connect_book.models.connect_book.md_to_html",
            side_effect=RuntimeError("boom"),
        ):
            self.assertIsNone(self.book._render_doc_html(filepath))

    # -- internal links ----------------------------------------------------

    def test_internal_link_is_rewritten_to_a_page_jump(self):
        html = self.book._rewrite_internal_links(
            '<a href="security.md" target="_blank" rel="noreferrer noopener">S</a>',
            "connect_sale",
            "index.md",
        )
        self.assertIn('data-book-page="connect_sale/security.md"', html)

    def test_internal_link_resolves_relative_to_the_current_page(self):
        html = self.book._rewrite_internal_links(
            '<a href="firewall.md#tr" target="_blank" rel="noreferrer noopener">F</a>',
            "connect_freeswitch",
            "admin/customer-onboarding.md",
        )
        self.assertIn(
            'data-book-page="connect_freeswitch/admin/firewall.md"', html
        )

    def test_internal_link_escaping_the_docs_folder_is_inert(self):
        html = self.book._rewrite_internal_links(
            '<a href="../../x.md" target="_blank" rel="noreferrer noopener">X</a>',
            "connect",
            "index.md",
        )
        self.assertNotIn("data-book-page", html)
        self.assertIn('<a href="#">', html)

    def test_external_link_is_left_alone(self):
        source = (
            '<a href="https://oduist.com" target="_blank" '
            'rel="noreferrer noopener">O</a>'
        )
        self.assertEqual(
            self.book._rewrite_internal_links(source, "connect", "index.md"), source
        )

    # -- access ------------------------------------------------------------

    def test_get_book_requires_connect_role(self):
        user = self.env["res.users"].create({
            "name": "No Connect Role",
            "login": "no.connect.role@example.com",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self.env["connect.book"].with_user(user).get_book()

    def test_get_admin_book_requires_connect_admin(self):
        user = self.env["res.users"].create({
            "name": "Connect User",
            "login": "connect.user.admin.book@example.com",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("connect.group_user").id,
            ])],
        })
        with self.assertRaises(AccessError):
            self.env["connect.book"].with_user(user).get_admin_book()

    def test_get_book_allows_connect_user_group(self):
        user = self.env["res.users"].create({
            "name": "Connect User",
            "login": "connect.user.book@example.com",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("connect.group_user").id,
            ])],
        })
        result = self.env["connect.book"].with_user(user).get_book()
        self.assertIn("modules", result)

    def test_get_admin_book_allows_connect_admin_group(self):
        self.assertIn("modules", self.book.get_admin_book())

    # -- assembling --------------------------------------------------------

    def test_collect_modules_returns_the_page_shape(self):
        self._write_mkdocs(
            "site_name: Fake\n"
            "nav:\n"
            "  - User Guide:\n"
            "      - Getting Started: user/start.md\n"
        )
        self._write_doc("user/start.md", "# Start\n")
        with self._patch_path():
            modules = self.book._collect_modules(AUDIENCE_USER, "en")
        self.assertTrue(modules)
        entry = modules[0]
        self.assertEqual(sorted(entry), ["id", "pages", "title"])
        self.assertEqual(entry["title"], "Fake")
        self.assertEqual(sorted(entry["pages"][0]), ["html", "id", "title"])
        self.assertTrue(entry["pages"][0]["id"].endswith("/user/start.md"))

    def test_collect_modules_skips_a_module_with_no_page_for_this_audience(self):
        self._write_mkdocs(
            "site_name: Fake\nnav:\n  - Setup: admin/setup.md\n"
        )
        self._write_doc("admin/setup.md", "# Setup\n")
        with self._patch_path():
            self.assertEqual(self.book._collect_modules(AUDIENCE_USER, "en"), [])
            self.assertTrue(self.book._collect_modules(AUDIENCE_ADMIN, "en"))

    def test_collect_modules_skips_a_module_without_mkdocs(self):
        self._write_doc("index.md", "# Orphan\n")
        with self._patch_path():
            self.assertEqual(self.book._collect_modules(AUDIENCE_ADMIN, "en"), [])

    # -- the changelog archive ---------------------------------------------

    def test_read_module_changes_returns_day_files_in_order(self):
        self._write_change("2026-08-18.md", "### Added\n\n- Later.\n")
        self._write_change("2026-08-03.md", "### Fixed\n\n- Earlier.\n")
        with self._patch_path():
            result = self.book._read_module_changes(self.module_path)
        self.assertEqual([date for date, _ in result], ["2026-08-03", "2026-08-18"])
        self.assertIn("Later.", result[1][1])

    def test_read_module_changes_ignores_a_file_that_is_not_a_day(self):
        self._write_change("2026-08-18.md", "### Added\n\n- Real.\n")
        self._write_change("README.md", "# Not a day\n")
        self._write_change("2026-8-3.md", "### Added\n\n- Malformed date.\n")
        with self._patch_path():
            result = self.book._read_module_changes(self.module_path)
        self.assertEqual([date for date, _ in result], ["2026-08-18"])

    def test_read_module_changes_without_the_folder_is_empty(self):
        with self._patch_path():
            self.assertEqual(self.book._read_module_changes(self.module_path), [])

    def test_get_changes_groups_by_day_most_recent_first(self):
        self._write_mkdocs("site_name: Fake\nnav:\n  - Overview: index.md\n")
        self._write_change("2026-08-03.md", "### Fixed\n\n- Earlier.\n")
        self._write_change("2026-08-18.md", "### Added\n\n- Later.\n")
        with self._patch_path():
            result = self.book.get_changes()
        dates = [day["date"] for day in result["days"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertIn("2026-08-18", dates)
        entry = result["days"][dates.index("2026-08-18")]["entries"][0]
        self.assertEqual(entry["title"], "Fake")
        self.assertIn("Later.", entry["html"])

    def test_get_changes_requires_connect_role(self):
        user = self.env["res.users"].create({
            "name": "No Connect Role",
            "login": "no.role.changes@example.com",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self.env["connect.book"].with_user(user).get_changes()

    def test_get_changes_allows_connect_user_group(self):
        user = self.env["res.users"].create({
            "name": "Connect User",
            "login": "connect.user.changes@example.com",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("connect.group_user").id,
            ])],
        })
        result = self.env["connect.book"].with_user(user).get_changes()
        self.assertIn("days", result)
