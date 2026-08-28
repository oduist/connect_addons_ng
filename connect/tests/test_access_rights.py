from odoo.tests import tagged, new_test_user
from odoo.exceptions import AccessError

from .common import ConnectTestCommon


@tagged('at_install', '-post_install')
class TestAccessRights(ConnectTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connect_admin_user = cls._create_connect_user('aradmin', cls.admin_user)

        cls.connect_user_user = new_test_user(
            cls.env,
            login='ar_connect_user',
            groups='base.group_user,connect.group_user',
        )
        cls.connect_admin = new_test_user(
            cls.env,
            login='ar_connect_admin',
            groups='base.group_user,connect.group_admin',
        )
        cls.webhook_user = new_test_user(
            cls.env,
            login='ar_connect_webhook',
            groups='base.group_user,connect.group_webhook',
        )
        # A connect.user owned by the plain Connect User, so the
        # "own records only" record rules let that user see it.
        cls.connect_user_own = cls._create_connect_user(
            'arown', cls.connect_user_user)

    # --- connect.call ---
    # group_user is restricted to its own calls by rule_connect_call_user
    # (caller_user / answered_user / called_users == user), so the records
    # under test are linked to connect_user_user.

    def test_call_user_can_read(self):
        """Connect user can read their own calls."""
        call = self._create_call(caller_user=self.connect_user_user.id)
        call.with_user(self.connect_user_user).read(['caller'])

    def test_call_user_can_create(self):
        """Connect user can create their own calls."""
        self.env['connect.call'].with_user(self.connect_user_user).with_context(
            tracking_disable=True,
        ).create({
            'caller': '+15550001111',
            'called': '+15550002222',
            'status': 'ringing',
            'direction': 'incoming',
            'caller_user': self.connect_user_user.id,
        })

    def test_call_user_cannot_unlink(self):
        """Connect user cannot delete calls."""
        call = self._create_call()
        with self.assertRaises(AccessError):
            call.with_user(self.connect_user_user).unlink()

    def test_call_admin_can_unlink(self):
        """Connect admin can delete calls."""
        call = self._create_call()
        call.with_user(self.connect_admin).unlink()

    # --- connect.channel ---

    def test_channel_user_can_read(self):
        """Connect user can read their own channels."""
        channel = self._create_channel(
            'ar_ch1', caller_user=self.connect_user_user.id)
        channel.with_user(self.connect_user_user).read(['sid'])

    def test_channel_user_cannot_create(self):
        """Connect user cannot create channels."""
        with self.assertRaises(AccessError):
            self.env['connect.channel'].with_user(self.connect_user_user).with_context(
                tracking_disable=True,
            ).create({
                'sid': 'ar_ch_fail',
                'caller': '+15550001111',
                'called': '+15550002222',
                'status': 'ringing',
                'technical_direction': 'inbound',
            })

    def test_channel_admin_can_create(self):
        """Connect admin can create channels."""
        self.env['connect.channel'].with_user(self.connect_admin).with_context(
            tracking_disable=True,
        ).create({
            'sid': 'ar_ch_admin',
            'caller': '+15550001111',
            'called': '+15550002222',
            'status': 'ringing',
            'technical_direction': 'inbound',
        })

    # --- connect.user ---

    def test_connect_user_user_can_read(self):
        """Connect user can read their own connect.user record."""
        self.connect_user_own.with_user(self.connect_user_user).read(['name'])

    def test_connect_user_user_cannot_create(self):
        """Connect user cannot create connect.user."""
        other = new_test_user(self.env, login='ar_unauthorized')
        with self.assertRaises(AccessError):
            self.env['connect.user'].with_user(self.connect_user_user).with_context(
                no_clear_cache=True,
            ).create({'user': other.id})

    def test_connect_user_admin_can_create(self):
        """Connect admin can create connect.user."""
        other = new_test_user(self.env, login='ar_admincreated')
        self.env['connect.user'].with_user(self.connect_admin).with_context(
            no_clear_cache=True,
        ).create({'user': other.id})

    def test_connect_user_webhook_can_read(self):
        """Webhook user can read PBX users required for call routing."""
        self.connect_user_own.with_user(self.webhook_user).read(['name'])

    def test_connect_user_webhook_cannot_write(self):
        """Webhook user cannot modify PBX user configuration."""
        with self.assertRaises(AccessError):
            self.connect_user_own.with_user(self.webhook_user).write({
                'name': 'Not allowed',
            })

    # --- connect.message ---

    def test_message_user_can_read(self):
        """Connect user can read messages."""
        msg = self.env['connect.message'].create({
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'status': 'received',
        })
        msg.with_user(self.connect_user_user).read(['body'])

    def test_message_user_cannot_unlink(self):
        """Connect user cannot delete messages."""
        msg = self.env['connect.message'].create({
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'status': 'received',
        })
        with self.assertRaises(AccessError):
            msg.with_user(self.connect_user_user).unlink()

    def test_message_admin_can_unlink(self):
        """Connect admin can delete messages."""
        msg = self.env['connect.message'].create({
            'from_number': '+15550001111',
            'to_number': '+15550002222',
            'status': 'received',
        })
        msg.with_user(self.connect_admin).unlink()

    # --- connect.recording ---

    def test_recording_user_read_only(self):
        """Connect user can read their own recordings but not create any."""
        rec = self.env['connect.recording'].with_context(
            skip_transcription=True).create({
            'duration': 30,
            'called_user': self.connect_user_user.id,
        })
        rec.with_user(self.connect_user_user).read(['duration'])
        with self.assertRaises(AccessError):
            self.env['connect.recording'].with_user(
                self.connect_user_user,
            ).with_context(skip_transcription=True).create({
                'duration': 10,
            })

    def test_recording_admin_full_access(self):
        """Connect admin has full access to recordings."""
        rec = self.env['connect.recording'].with_user(
            self.connect_admin,
        ).with_context(skip_transcription=True).create({
            'duration': 10,
        })
        rec.with_user(self.connect_admin).unlink()

    # --- connect.settings ---

    def test_settings_user_cannot_read(self):
        """Connect user has no access to the admin-only settings model."""
        settings = self.env['connect.settings'].search([])
        if settings:
            with self.assertRaises(AccessError):
                settings.with_user(self.connect_user_user).read(['debug_mode'])

    def test_settings_user_cannot_write(self):
        """Connect user cannot write settings."""
        settings = self.env['connect.settings'].search([])
        if settings:
            with self.assertRaises(AccessError):
                settings.with_user(self.connect_user_user).write(
                    {'debug_mode': True})

    # --- connect.favorite ---

    def test_favorite_user_full_access(self):
        """Connect user has full CRUD on favorites."""
        fav = self.env['connect.favorite'].with_user(
            self.connect_user_user).create({
            'phone_number': '+15559990000',
            'name': 'My Fav',
        })
        fav.with_user(self.connect_user_user).write({'name': 'Updated'})
        fav.with_user(self.connect_user_user).unlink()

    # --- partner form stat buttons ---
    # The Calls / Messages counts are computed with sudo(), so the buttons
    # would otherwise render for every internal user and only fail with an
    # AccessError once clicked. They must be filtered out of the arch.

    def _partner_form_arch(self, user):
        return self.env['res.partner'].with_user(user).get_view(
            self.env.ref('base.view_partner_form').id, 'form')['arch']

    def test_partner_form_hides_stat_buttons_from_plain_user(self):
        """A user outside the Connect groups is not served the stat buttons."""
        arch = self._partner_form_arch(self.basic_user)
        self.assertNotIn('connect_calls_count', arch)
        self.assertNotIn('connect_messages_count', arch)

    def test_partner_form_shows_stat_buttons_to_connect_user(self):
        """A Connect user still gets both stat buttons."""
        arch = self._partner_form_arch(self.connect_user_user)
        self.assertIn('connect_calls_count', arch)
        self.assertIn('connect_messages_count', arch)

    # --- res.users.connect_user ---
    # The field is computed by searching connect.user, which only the Connect
    # groups may read. It must resolve with compute_sudo, otherwise every
    # internal user outside those groups hits an AccessError just reading
    # their own record (own preferences, or any read() covering the field).

    def test_connect_user_field_readable_by_plain_user(self):
        """A user outside the Connect groups can read res.users.connect_user."""
        user = self.basic_user
        self.assertFalse(
            user.has_group('connect.group_user'),
            'basic_user must stay outside the Connect groups for this test')
        user.with_user(user).read(['name', 'connect_user'])

    def test_connect_user_field_resolves_for_connect_user(self):
        """The field still points at the caller's own connect.user record."""
        owner = self.connect_user_user
        self.assertEqual(
            owner.with_user(owner).connect_user, self.connect_user_own)
