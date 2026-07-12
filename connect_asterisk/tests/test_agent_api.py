# -*- coding: utf-8 -*-
"""Agent bootstrap / dialplan-assist controller tests."""
from odoo.tests import tagged, HttpCase

from .common import AGENT_TOKEN


@tagged('post_install', '-at_install', 'connect_asterisk')
class TestAgentAPI(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env['connect.settings']
        cls.Settings.set_param('asterisk_agent_token', AGENT_TOKEN)
        cls.Settings.set_param('asterisk_ami_user', 'connect-agent')
        cls.Settings.set_param('asterisk_ami_password', 'ami-secret')
        cls.partner = cls.env['res.partner'].with_context(
            no_clear_cache=True).create({
                'name': 'API Test Partner',
                'phone': '+15557778888',
            })
        cls.odoo_user = cls.env['res.users'].create({
            'name': 'API User', 'login': 'ast_api_user'})
        cls.connect_user = cls.env['connect.user'].with_context(
            no_clear_cache=True).create({'user': cls.odoo_user.id})
        cls.endpoint = cls.env['connect.asterisk.endpoint'].create({
            'name': 'API endpoint',
            'connect_user_id': cls.connect_user.id,
            'asterisk_channel': 'PJSIP/201',
            'asterisk_sip_transport': 'webrtc',
        })

    def _get(self, path, token=AGENT_TOKEN, bearer=True):
        headers = {}
        if token and bearer:
            headers['Authorization'] = 'Bearer %s' % token
        elif token:
            sep = '&' if '?' in path else '?'
            path = '%s%stoken=%s' % (path, sep, token)
        return self.url_open(path, headers=headers)

    def test_config_requires_token(self):
        self.assertEqual(
            self._get('/asterisk/api/config', token=None).status_code, 401)

    def test_config_payload(self):
        response = self._get('/asterisk/api/config')
        self.assertEqual(response.status_code, 200)
        config = response.json()
        self.assertEqual(config['ami']['user'], 'connect-agent')
        self.assertEqual(config['ami']['password'], 'ami-secret')
        self.assertIn('Newchannel', config['events'])

    def test_token_accepted_as_query_param(self):
        response = self._get('/asterisk/api/config', bearer=False)
        self.assertEqual(response.status_code, 200)

    def test_get_caller_name(self):
        response = self._get(
            '/asterisk/api/get_caller_name?number=%2B15557778888')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'API Test Partner')
        response = self._get('/asterisk/api/get_caller_name?number=999')
        self.assertEqual(response.text, '')

    def test_get_partner_manager(self):
        self.partner.user_id = self.odoo_user
        response = self._get(
            '/asterisk/api/get_partner_manager?number=%2B15557778888')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, 'PJSIP/201')

    def test_sip_peers(self):
        response = self._get('/asterisk/api/sip_peers')
        self.assertEqual(response.status_code, 200)
        self.assertIn('[webrtc-user](!)', response.text)
        self.assertIn('[201](webrtc-user)', response.text)
        self.assertIn('inbound_auth/username = 201', response.text)

    def test_manager_conf(self):
        response = self._get('/asterisk/api/manager_conf')
        self.assertEqual(response.status_code, 200)
        self.assertIn('[connect-agent]', response.text)
        self.assertIn('secret = ami-secret', response.text)
        self.assertIn('read = call,dialplan,user', response.text)
