# -*- coding: utf-8 -*-
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

from odoo.tests import TransactionCase, new_test_user

# Throwaway RSA key used only for JWT tests (never a real credential).
TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCz2cpda1lyHhAB
woSGjLgwzT+ZdpWJm7aRYNoemIJmBeS/rhw8T7fMJIsjvbIwZimqVCcxBuO5r1op
IFLszVO+gouBQ9yGliHE5nsP3UbtavSMuEb4US8H62+2+obxSikOOEsa0IRGLAve
IazIHs9yE1m6tksc6HCW3c/JM0yV/Cpp3nRQfh3I6CYqk+FF1nFDMYu910o1iaCQ
vv3nE6S08EbFWq6hpVeDsV4w3u17BG7YX584qhh6fWB3re0kTRAnty+2OKDh8Rko
wyFvwN7x0r4vkY/5UNerButAUXnlJS2qjcdtF7lPkUDlOqW50Bfidv/KU1E/57CM
Uli/HdiZAgMBAAECggEAD7axpaPhdsUFpQG3zoGw/iKQsfnYauN9+gm6RP4SNpPB
PrYZpXNZna57sa27SdtDPKyJmBEACJM3j2xRknsGHBkP00V4mRG49Zklm2c78TZt
E3ZuTPfa4hhB9HzDGYXfPGzSsw8Q34itqMTMcdevTEpAhr2ypl3wqF3M78lZoaj2
j4KufGhZdmIOVvNXQiQNAiMtvB7a8XaF9hyY6cFYZBXdPg0teKiVES20RM5HDRym
WAp56gZVyORaRwsP8OtFwuCsiTLhwsO5whLYF+eNwQv7wEVKvoLwDxYBL+XtIQrd
z1hdrkGsAi3p1HvQQ3Pt1ok0S7r1h6Vy65aO7Li6AQKBgQD9c2339CiDBLZ23LQk
/JhC/bYN6tymyJE1aZ3BcCj+ZH+n+usWHefO1DhSgge4luPdjWV1/af2g8yGXKzK
VelUGNRTEknVx1TDS7Ko4jDFIyZya9mYwCk6GdA6ZpQUpGKBIihP2BZ1pmqZqHUh
CJ4g4SGmTSqtPMYfEQX1Ztc5oQKBgQC1qNwN4eK1vMtFNgOVDitaE8Ii6y9B25pJ
3IgFAqnQ5uq0QSmalBnp5F9/RqVRiCF8bYt3Fw06lnjqDHWDMsASVqsXklf+ceeC
8EMSw2hTXWTQ++pDDrIvlWnTMN8PR7wypfxEaGo6R1UmR+AKq9JSGZuu7fJO8yvT
bL8tGeDr+QKBgQCGgyKT/DMcBf5I6y14i87Ljxd2H3Xn1n6qmFkvdrVq/i96GYN3
A3wpmxwhPf2XDA33Ybm9e1gPTzfW/4x8/keNaHgXdpdVLCtiUuSJGTLFDbiz9WVQ
2nuG6HhI5nQk2HGnE1fNuGODIUVmM6+mToqN7K4NMts5gg2sIz7EVUZYwQKBgFaa
pi5IHlkeJJpeYd7R3oEXIlqbXPA8zZWg+YfJ+UOKkyJUXo0/RgtnwM9g0rfH+o7j
erXP25Ku4f5S6kMeEsurXe3i6uh3TTPzb0amujnkMIghUVGe0/wzczwn9G/Id0R+
NYI3dU1LbKDPa1QrDh3t73a6IebZr28gTRQnXj+hAoGBALhqfxn7APrD1xkPhruS
6NaIdBbJ+lrU7D2AzIkTsXOApFIhc1j2BDX4XiMiuUiwpUbG1p7oa4vzIYOHBryt
7QQwsD4X/fmu9w9BIDh8Lzgu/9Gbptn0uw4fpUFF13lasrRC5es6I6+Y/ZMVq0Gb
OJzY7FayVeJadwR35b93m2X8
-----END PRIVATE KEY-----"""


def make_channel_event(uuid='leg-1', conversation_uuid='conv-1',
                       from_='15550002222', to='15550001111',
                       status='started', direction='inbound', **kwargs):
    event = {
        'uuid': uuid,
        'conversation_uuid': conversation_uuid,
        'from': from_,
        'to': to,
        'status': status,
        'direction': direction,
        'timestamp': '2026-07-11T10:00:00.000Z',
    }
    event.update(kwargs)
    return event


class VonageTestCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'connect.api_url', 'https://odoo.example.com/')
        cls.settings = cls.env['connect.settings'].sudo()
        # Seed the singleton: fake credentials, verification and auto
        # sync off so tests never hit the network.
        cls.settings.set_param('vonage_api_key', 'testkey')
        cls.settings.set_param('vonage_api_secret', 'testsecret')
        cls.settings.set_param('vonage_application_id', 'app-test-id')
        cls.settings.set_param('vonage_private_key', TEST_PRIVATE_KEY)
        cls.settings.set_param('vonage_signature_secret', 'sigsecret123')
        cls.settings.set_param('vonage_verify_requests', False)
        cls.settings.set_param('vonage_auto_sync', False)
        cls.partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': 'Test Partner',
                'email': 'test@example.com',
                'phone': '+15550002222',
            })

    @classmethod
    def _create_connect_user(cls, login, **kwargs):
        odoo_user = new_test_user(cls.env, login=login)
        vals = {'user': odoo_user.id, 'username': login.replace('_', '')}
        vals.update(kwargs)
        return cls.env['connect.user'].with_context(
            no_clear_cache=True, no_vonage_create=True).create(vals)

    @contextmanager
    def mock_license_check(self, result=True):
        with patch.object(
            type(self.env['oduist.license']),
            'check_license',
            return_value=result,
        ):
            yield

    @contextmanager
    def mock_vonage_client(self):
        mock_client = MagicMock()
        with patch.object(
            type(self.env['connect.settings']),
            'get_client',
            return_value=mock_client,
        ):
            yield mock_client
