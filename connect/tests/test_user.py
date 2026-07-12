from odoo.tests import tagged
from odoo.exceptions import ValidationError

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestConnectUser(ConnectTestCommon):
    """Tests for the core connect.user model.

    Core connect.user identifies a user purely by its linked res.users
    (the `user` Many2one). SIP/client username matching, the alphanumeric
    `username` field and URI-based lookup are added by provider modules
    (connect_twilio) and are covered by their own suites.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_user = cls._create_connect_user('testuser1', cls.admin_user)

    def test_create_user(self):
        """Test basic connect.user creation links the Odoo user."""
        self.assertTrue(self.connect_user.id)
        self.assertEqual(self.connect_user.user, self.admin_user)

    def test_name_compute_with_odoo_user(self):
        """Test computed name uses the linked Odoo user name."""
        self.assertEqual(self.connect_user.name, self.admin_user.name)

    def test_unique_odoo_user(self):
        """Test that the same Odoo user can't be linked twice."""
        with self.assertRaises(Exception), self.cr.savepoint():
            self._create_connect_user('testuser2', self.admin_user)

    def test_group_assignment_admin(self):
        """Admin Odoo users get connect.group_admin on create."""
        group_admin = self.env.ref('connect.group_admin')
        self.assertIn(self.admin_user, group_admin.user_ids)

    def test_group_assignment_basic_user(self):
        """Basic Odoo users get connect.group_user on create."""
        self._create_connect_user('basicpbx', self.basic_user)
        group_user = self.env.ref('connect.group_user')
        self.assertIn(self.basic_user, group_user.user_ids)

    def test_group_removal_on_unlink(self):
        """Groups are removed when connect user is deleted."""
        user = self._create_connect_user('tempuser', self.basic_user)
        group_user = self.env.ref('connect.group_user')
        self.assertIn(self.basic_user, group_user.user_ids)
        user.unlink()
        self.assertNotIn(self.basic_user, group_user.user_ids)

    def test_get_user_by_uri_no_op_in_core(self):
        """Core get_user_by_uri returns empty (overridden by provider modules)."""
        result = self.env['connect.user'].get_user_by_uri('sip:testuser1@domain.com')
        self.assertFalse(result)

    def test_get_user_by_uri_none(self):
        """Test URI resolution handles None input."""
        result = self.env['connect.user'].get_user_by_uri(None)
        self.assertFalse(result)

    def test_get_user_by_exten_number_no_match(self):
        """Provider-neutral search: no crash, False when nothing matches.

        The searched fields come from provider modules via
        _pbx_number_fields(); with no provider installed the list is empty
        and the method returns False."""
        result = self.env['connect.user'].with_user(
            self.admin_user).get_user_by_exten_number('no-such-exten-xyz')
        self.assertFalse(result)

    def test_get_user_by_exten_number_no_group(self):
        """Test non-connect users cannot search by extension."""
        with self.assertRaises(ValidationError):
            self.env['connect.user'].with_user(
                self.portal_user).get_user_by_exten_number('8101')

    def test_default_record_calls(self):
        """Test record_calls defaults to True."""
        self.assertTrue(self.connect_user.record_calls)

    def test_default_active(self):
        """Test active defaults to True."""
        self.assertTrue(self.connect_user.active)

    def test_default_prompt_language(self):
        """TTS prompt language defaults to en-US (ADR-037)."""
        self.assertEqual(self.connect_user.language, 'en-US')

    def test_default_voice_empty(self):
        """Voice is empty by default: providers apply their own default."""
        self.assertFalse(self.connect_user.voice)

    def test_language_selection_list(self):
        """The BCP-47 list has the 26 agreed entries (ADR-037)."""
        selection = self.env['connect.user']._get_language_selection()
        codes = [code for code, _label in selection]
        self.assertEqual(len(codes), 26)
        self.assertIn('en-US', codes)
        self.assertIn('de-DE', codes)
        self.assertIn('zh-CN', codes)
