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
