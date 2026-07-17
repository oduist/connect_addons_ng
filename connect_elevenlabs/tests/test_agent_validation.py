# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestAgentValidation(TransactionCase):

    def test_stability_rejects_values_above_one(self):
        agent = self.env['connect.elevenlabs_agent'].new({
            'stability': 1.5,
            'temperature': 0.5,
        })

        with self.assertRaises(ValidationError):
            agent._check_stability()

    def test_similarity_boost_rejects_values_above_one(self):
        agent = self.env['connect.elevenlabs_agent'].new({
            'similarity_boost': 1.5,
        })

        with self.assertRaises(ValidationError):
            agent._check_similarity_boost()
