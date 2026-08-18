from contextlib import contextmanager
from unittest.mock import patch, MagicMock

from odoo.tests import TransactionCase, new_test_user


class ConnectTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_test_users()
        cls._setup_test_data()

    @classmethod
    def _setup_test_users(cls):
        cls.admin_user = new_test_user(
            cls.env,
            login='connect_admin',
            groups='base.group_user,base.group_system,base.group_erp_manager',
        )
        cls.basic_user = new_test_user(
            cls.env,
            login='connect_basic',
            groups='base.group_user',
        )
        cls.portal_user = new_test_user(
            cls.env,
            login='connect_portal',
            groups='base.group_portal',
        )

    @classmethod
    def _setup_test_data(cls):
        cls.partner = cls.env['res.partner'].with_context(no_clear_cache=True).create({
            'name': 'Test Partner',
            'email': 'test@example.com',
            'phone': '+15551234567',
        })
        cls.partner2 = cls.env['res.partner'].with_context(no_clear_cache=True).create({
            'name': 'Test Partner 2',
            'email': 'test2@example.com',
            'phone': '+15559876543',
        })

    @classmethod
    def _create_connect_user(cls, username, odoo_user=None, **kwargs):
        # Core connect.user has no `username` field (it is added by
        # connect_twilio) and requires a linked res.users. Auto-create an
        # Odoo user from the given handle when none is supplied so the
        # helper builds a valid core record.
        if odoo_user is None:
            odoo_user = new_test_user(cls.env, login=username)
        vals = {'user': odoo_user.id}
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(no_clear_cache=True).create(vals)

    @classmethod
    def _create_channel(cls, sid, caller='+15551111111', called='+15552222222', **kwargs):
        vals = {
            'sid': sid,
            'caller': caller,
            'called': called,
            'status': 'ringing',
            'technical_direction': 'inbound',
            'call_type': 'phone',
        }
        vals.update(kwargs)
        return cls.env['connect.channel'].with_context(tracking_disable=True).create(vals)

    @classmethod
    def _create_call(cls, caller='+15551111111', called='+15552222222', **kwargs):
        vals = {
            'caller': caller,
            'called': called,
            'status': 'ringing',
            'direction': 'incoming',
        }
        vals.update(kwargs)
        return cls.env['connect.call'].with_context(tracking_disable=True).create(vals)

    @contextmanager
    def mock_license_check(self, result=True):
        with patch.object(
            type(self.env['oduist.license']),
            'check_license',
            return_value=result,
        ):
            yield

    @contextmanager
    def mock_openai_client(
        self,
        transcript_text='Test transcript',
        summary_text='Test summary',
        transcript_duration=60,
    ):
        mock_client = MagicMock()
        mock_transcript = MagicMock()
        mock_transcript.segments = []
        mock_transcript.duration = transcript_duration
        mock_client.audio.transcriptions.create.return_value = mock_transcript

        mock_summary = MagicMock()
        mock_summary.choices = [MagicMock()]
        mock_summary.choices[0].message.content = summary_text
        mock_summary.usage = 'test_usage'
        mock_client.chat.completions.create.return_value = mock_summary

        with patch.object(
            type(self.env['connect.settings']),
            'get_openai_client',
            return_value=mock_client,
        ):
            yield mock_client

    @contextmanager
    def mock_connect_reload_view(self):
        with patch.object(
            type(self.env['connect.settings']),
            'connect_reload_view',
        ):
            yield
