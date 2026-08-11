# -*- coding: utf-8 -*-
"""Softphone i18n catalog tests (ADR-038).

Reads the shipped po files through Odoo's code-translation loader, which
is exactly the path the web client uses for JS/OWL terms. A malformed po
entry (missing ``#. module:`` comment, bad occurrence line) would make
the loader fail or silently drop the term — both are caught here.
"""
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import code_translations


@tagged('post_install', '-at_install', 'connect_freeswitch')
class TestSoftphoneI18n(TransactionCase):
    # fr_CH / it_CH prove the base-language fallback (fr.po / it.po).
    LANGS = ['de_DE', 'fr_CH', 'it_CH', 'ru_RU']
    EXPECTED = [
        'Ready', 'Incoming call', 'Enter number', 'Free',
        'No parking slots configured.', 'Show password',
    ]

    def test_web_translations_load(self):
        for lang in self.LANGS:
            bundle = code_translations.get_web_translations(
                'connect_freeswitch', lang)
            messages = {m['id']: m['string'] for m in bundle['messages']}
            for msgid in self.EXPECTED:
                self.assertIn(msgid, messages,
                              '%s: missing %r' % (lang, msgid))
                self.assertTrue(messages[msgid],
                                '%s: empty translation for %r' % (lang, msgid))

    def test_python_translations_load(self):
        for lang in self.LANGS:
            translations = code_translations.get_python_translations(
                'connect_freeswitch', lang)
            self.assertIn('Call parked on slot %s', translations,
                          '%s: missing python term' % lang)
            self.assertTrue(translations['Call parked on slot %s'])
