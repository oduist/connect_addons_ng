# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInitiationPayload(TransactionCase):
    """`build_initiation_payload` is what the conversation-initiation webhook
    returns to ElevenLabs. It must always yield a valid envelope and resolve
    dynamic variables through the retargeted models (connect.user.twilio_exten,
    connect.twilio.exten.is_published, res.partner) — no ElevenLabs API call.
    """

    def _payload(self, **kw):
        return self.env["connect.elevenlabs_agent"].build_initiation_payload(**kw)

    def test_envelope_and_variables(self):
        payload = self._payload(caller="+15551234567", called="+15559999999")
        self.assertEqual(payload["type"], "conversation_initiation_client_data")
        dyn = payload["dynamic_variables"]
        for key in ("call_id", "caller_number", "called_number", "partner_name",
                    "existing_partner", "partner_phone", "greeting",
                    "previous_topics", "available_extensions", "users_directory"):
            self.assertIn(key, dyn)
        self.assertEqual(dyn["caller_number"], "+15551234567")
        self.assertEqual(dyn["called_number"], "+15559999999")

    def test_unknown_caller_is_not_registered(self):
        dyn = self._payload(caller="+19998887777", called="+15559999999")["dynamic_variables"]
        self.assertEqual(dyn["existing_partner"], "No")
        self.assertEqual(dyn["partner_name"], "Not registered")

    def test_known_partner_resolved(self):
        self.env["res.partner"].create({"name": "Jane Caller", "phone": "+15551110000"})
        dyn = self._payload(caller="+15551110000", called="+15559999999")["dynamic_variables"]
        self.assertEqual(dyn["existing_partner"], "Yes")
        self.assertEqual(dyn["partner_name"], "Jane Caller")

    def test_published_extension_listed(self):
        # is_published is the field the add-on re-adds to connect.twilio.exten.
        self.env["connect.twilio.exten"].create({
            "number": "7001", "is_published": True,
        })
        dyn = self._payload(caller="+15551234567", called="+15559999999")["dynamic_variables"]
        self.assertIn("7001", dyn["available_extensions"])
