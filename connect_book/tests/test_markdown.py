# -*- coding: utf-8 -*-
from odoo.tests.common import BaseCase
from odoo.tests import tagged

from odoo.addons.connect_book.models.markdown import md_to_html


@tagged("post_install", "-at_install", "connect_book")
class TestMarkdown(BaseCase):
    def test_heading_and_paragraph(self):
        html = md_to_html("# Title\n\nHello world\n")
        self.assertIn('<h1 id="title">Title</h1>', html)
        self.assertIn("<p>Hello world</p>", html)

    def test_unordered_list(self):
        html = md_to_html("- one\n- two\n")
        self.assertIn("<ul>", html)
        self.assertEqual(html.count("<li>"), 2)

    def test_fenced_code_block_is_not_interpreted(self):
        html = md_to_html("```python\n# not a heading\n```\n")
        self.assertIn("<pre>", html)
        self.assertNotIn("<h1>", html)

    def test_table(self):
        html = md_to_html("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        self.assertIn("<table>", html)
        self.assertIn("<th>", html)

    def test_html_is_escaped(self):
        html = md_to_html("<script>alert(1)</script>\n")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_javascript_url_is_neutralised(self):
        html = md_to_html("[click](javascript:alert(1))\n")
        self.assertNotIn("javascript:", html)
        self.assertIn('href="#"', html)

    def test_https_url_is_kept(self):
        html = md_to_html("[docs](https://oduist.com/docs)\n")
        self.assertIn('href="https://oduist.com/docs"', html)

    def test_list_switches_from_unordered_to_ordered_at_same_indent(self):
        html = md_to_html("- a\n- b\n1. c\n2. d\n")
        for item in ("a", "b", "c", "d"):
            self.assertIn("<li>%s</li>" % item, html)
        self.assertIn("<ul>", html)
        self.assertIn("<ol>", html)

    def test_list_switches_from_ordered_to_unordered_at_same_indent(self):
        html = md_to_html("1. a\n2. b\n- c\n- d\n")
        for item in ("a", "b", "c", "d"):
            self.assertIn("<li>%s</li>" % item, html)
        self.assertIn("<ol>", html)
        self.assertIn("<ul>", html)

    def test_nested_list_is_not_broken_by_the_kind_switch_fix(self):
        html = md_to_html("- a\n  - b\n  - c\n- d\n")
        # "a" is followed by a nested <ul>, not a closing </li>, so match on
        # its text boundaries rather than assuming an immediate </li>.
        self.assertIn(">a<", html)
        self.assertIn("<li>b</li>", html)
        self.assertIn("<li>c</li>", html)
        self.assertIn("<li>d</li>", html)
        self.assertEqual(html.count("<ul>"), 2)

    # -- MkDocs constructs -------------------------------------------------

    def test_admonition_with_title(self):
        html = md_to_html('!!! warning "Careful"\n    Do not do this.\n')
        self.assertIn("o_book_admonition_warning", html)
        self.assertIn(
            '<p class="o_book_admonition_title">Careful</p>', html
        )
        self.assertIn("<p>Do not do this.</p>", html)

    def test_admonition_without_title_uses_the_kind(self):
        html = md_to_html("!!! note\n    Just so you know.\n")
        self.assertIn('<p class="o_book_admonition_title">Note</p>', html)

    def test_admonition_body_is_rendered_as_markdown(self):
        html = md_to_html(
            '!!! info "Scope"\n'
            "    Only **customer** invoices:\n"
            "\n"
            "    - posted\n"
            "    - unpaid\n"
        )
        self.assertIn("<strong>customer</strong>", html)
        self.assertIn("<li>posted</li>", html)
        self.assertIn("<li>unpaid</li>", html)

    def test_admonition_ends_at_the_next_unindented_line(self):
        html = md_to_html("!!! note\n    Inside.\n\nOutside.\n")
        self.assertIn("<p>Inside.</p></div>", html)
        self.assertTrue(html.rstrip().endswith("<p>Outside.</p>"))

    def test_unknown_admonition_kind_falls_back_to_note(self):
        html = md_to_html('!!! quote "Someone"\n    Words.\n')
        self.assertIn("o_book_admonition_note", html)

    def test_content_tabs_are_grouped(self):
        html = md_to_html(
            '=== "Twilio"\n'
            "    Use `/twilio/webhook`.\n"
            "\n"
            '=== "Telnyx"\n'
            "    Use `/telnyx/webhook`.\n"
        )
        self.assertEqual(html.count('<div class="o_book_tabs">'), 1)
        self.assertEqual(html.count('<div class="o_book_tab">'), 2)
        self.assertIn('<p class="o_book_tab_label">Twilio</p>', html)
        self.assertIn("<code>/telnyx/webhook</code>", html)

    def test_content_tabs_stop_at_following_content(self):
        html = md_to_html('=== "One"\n    First.\n\nAfter the tabs.\n')
        self.assertIn("</div></div>", html)
        self.assertTrue(html.rstrip().endswith("<p>After the tabs.</p>"))
