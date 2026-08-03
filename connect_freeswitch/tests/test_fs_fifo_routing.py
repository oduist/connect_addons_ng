# -*- coding: utf-8 -*-
"""FS Queue reachability and mod_fifo refresh (ADR-048, ADR-049).

Two bugs made the "Fallback Queue" of a callflow useless (issue #117):

* ODU-43 — a queue has no ``connect.freeswitch.exten`` until an admin creates
  one by hand, so ``fifo_number`` was empty and the ``{% if fifo_number %}``
  transfer block was silently dropped from the ring-group / IVR dialplan: the
  caller was hung up instead of queued. The standalone path did emit a
  transfer, but to a bare record id that no route ever matched.
* ODU-44 — mod_fifo reads its outbound ``<member>`` consumers from fifo.conf
  only at (re)load, so agents edited in Odoo were never rung until a manual
  ``reload mod_fifo``.

The queue is now routed by the internal ``fs_fifo_<id>`` handle, and member
changes schedule a post-commit reload.
"""
import base64
from unittest import mock

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import FsTestCommon


class FsFifoCommon(FsTestCommon):
    """Queue helpers shared by the routing and reload cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fifo = cls.env['connect.fs_fifo']
        cls.Callflow = cls.env['connect.freeswitch.callflow']
        cls.Exten = cls.env['connect.freeswitch.exten']

    @classmethod
    def _create_fifo(cls, name='Support', number=None):
        """Create a queue, optionally with a user-facing extension."""
        fifo = cls.Fifo.create({'name': name})
        if number:
            exten = cls.Exten.create({
                'number': number,
                'model': 'connect.fs_fifo',
                'res_id': fifo.id,
            })
            fifo.exten = exten
            fifo.invalidate_recordset()
        return fifo

    def _create_user_exten(self, login, number):
        user = self._create_connect_user(login)
        exten = self.Exten.create({
            'number': number,
            'model': 'connect.user',
            'res_id': user.id,
        })
        user.freeswitch_exten = exten
        user.invalidate_recordset()
        return user


@tagged('at_install', '-post_install')
class TestFsQueueDialplanTarget(FsFifoCommon):
    """A queue must be routable with or without its own extension (ADR-048)."""

    def test_dialplan_target_is_handle_without_extension(self):
        fifo = self._create_fifo('No Exten Queue')
        self.assertFalse(fifo.exten_number)
        self.assertEqual(fifo._dialplan_target(), 'fs_fifo_%d' % fifo.id)

    def test_dialplan_target_prefers_extension(self):
        fifo = self._create_fifo('Numbered Queue', number='763')
        self.assertEqual(fifo._dialplan_target(), '763')

    def test_queue_dialplan_self_names_by_handle(self):
        """The rendered condition must match the handle it is transferred to."""
        fifo = self._create_fifo('Handle Queue')
        xml = fifo.generate_dialplan({})
        self.assertIn('expression="^fs_fifo_%d$"' % fifo.id, xml)

    def test_queue_dialplan_uses_extension_when_assigned(self):
        fifo = self._create_fifo('Numbered Queue', number='764')
        xml = fifo.generate_dialplan({})
        self.assertIn('expression="^764$"', xml)
        self.assertNotIn('fs_fifo_%d$' % fifo.id, xml)


@tagged('at_install', '-post_install')
class TestFsQueueCallflowFallback(FsFifoCommon):
    """The three callflow paths must always emit the fallback transfer."""

    def _expected_transfer(self, fifo):
        return 'transfer" data="fs_fifo_%d XML default"' % fifo.id

    def test_ring_group_fallback_transfers_to_handle(self):
        """The regression: an extension-less queue used to be dropped here."""
        user = self._create_user_exten('fs_fifo_rg_user', '471')
        fifo = self._create_fifo('RG Fallback')
        callflow = self.Callflow.create({
            'name': 'RG with queue',
            'ring_users': [Command.set([user.id])],
            'fs_fifo_id': fifo.id,
        })

        xml = callflow.generate_dialplan({}, exten=None)

        self.assertIn('application="bridge"', xml)
        self.assertIn(self._expected_transfer(fifo), xml)

    def test_ivr_no_choice_default_transfers_to_handle(self):
        target = self.Exten.create({'number': '472'})
        fifo = self._create_fifo('IVR Fallback')
        callflow = self.Callflow.create({
            'name': 'IVR with queue',
            'gather_input': True,
            'prompt_message': 'Press one.',
            'choices': [Command.create({
                'choice_digits': '1',
                'exten': target.id,
            })],
            'fs_fifo_id': fifo.id,
        })

        xml = callflow.generate_dialplan({}, exten=None)

        self.assertIn('bind_digit_action', xml)
        self.assertIn(self._expected_transfer(fifo), xml)

    def test_standalone_callflow_transfers_to_handle(self):
        """Was a dead ``str(id)`` target that no route ever matched."""
        fifo = self._create_fifo('Standalone Fallback')
        callflow = self.Callflow.create({
            'name': 'Queue wrapper',
            'fs_fifo_id': fifo.id,
        })

        xml = callflow.generate_dialplan({}, exten=None)

        self.assertIn(self._expected_transfer(fifo), xml)
        self.assertNotIn('data="%d XML default"' % fifo.id, xml)

    def test_extension_still_wins_over_handle(self):
        user = self._create_user_exten('fs_fifo_rg_user2', '473')
        fifo = self._create_fifo('Numbered Fallback', number='765')
        callflow = self.Callflow.create({
            'name': 'RG with numbered queue',
            'ring_users': [Command.set([user.id])],
            'fs_fifo_id': fifo.id,
        })

        xml = callflow.generate_dialplan({}, exten=None)

        self.assertIn('transfer" data="765 XML default"', xml)
        self.assertNotIn('fs_fifo_%d' % fifo.id, xml)


@tagged('post_install', '-at_install', 'connect_freeswitch', 'fs_fifo')
class TestFsQueueHandleRouting(HttpCase):
    """The dialplan controller must resolve fs_fifo_<id> back to the queue."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env['connect.settings']
        cls.token = cls.Settings.sudo().get_param('freeswitch_webhook_token')
        if not cls.token:
            cls.token = 'test-token-test-token-test-token'
            cls.Settings.sudo().set_param('freeswitch_webhook_token', cls.token)
        # Queue writes schedule a post-commit reload (ADR-049); keep every
        # FreeSWITCH call in this class in-process.
        patcher = mock.patch.object(
            type(cls.Settings), 'freeswitch_api', return_value='OK')
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        cls.fifo = cls.env['connect.fs_fifo'].create({'name': 'Routed Queue'})
        cls.env.flush_all()

    def _lookup_dialplan(self, destination):
        """POST the xml_curl dialplan lookup FreeSWITCH sends on a transfer."""
        cred = base64.b64encode(
            ('freeswitch:%s' % self.token).encode()).decode()
        resp = self.url_open(
            '/freeswitch/xml',
            data={
                'section': 'dialplan',
                'Hunt-Context': 'default',
                'Hunt-Destination-Number': destination,
                'Caller-Destination-Number': destination,
            },
            headers={'Authorization': 'Basic %s' % cred},
        )
        self.assertEqual(resp.status_code, 200)
        return resp.text

    def test_handle_routes_to_queue_dialplan(self):
        body = self._lookup_dialplan('fs_fifo_%d' % self.fifo.id)
        self.assertIn('<extension name="fs_fifo_%d">' % self.fifo.id, body)
        self.assertIn('expression="^fs_fifo_%d$"' % self.fifo.id, body)
        self.assertIn('application="fifo"', body)

    def test_unknown_handle_does_not_route_to_a_queue(self):
        """A stale handle must fall through the normal lookup, not crash."""
        missing = self.env['connect.fs_fifo'].search(
            [], order='id desc', limit=1).id + 1000
        body = self._lookup_dialplan('fs_fifo_%d' % missing)
        self.assertNotIn('<extension name="fs_fifo_%d">' % missing, body)


@tagged('at_install', '-post_install')
class TestFsQueueModFifoReload(FsFifoCommon):
    """Member/config changes must refresh mod_fifo after commit (ADR-049)."""

    def _patch_api(self, side_effect=None):
        """Record every freeswitch_api call instead of reaching FreeSWITCH."""
        calls = []

        def fake_api(command, args=''):
            calls.append((command, args))
            if side_effect:
                raise side_effect
            return 'OK'

        patcher = mock.patch.object(
            type(self.env['connect.settings']), 'freeswitch_api',
            side_effect=fake_api)
        return calls, patcher

    def test_create_defers_reload_to_postcommit(self):
        calls, patcher = self._patch_api()
        with patcher:
            self._create_fifo('Reload On Create')
            # Deferred: FreeSWITCH must not be touched inside the transaction,
            # it re-reads fifo.conf over xml_curl on a separate connection.
            self.assertEqual(calls, [])
            self.env.cr.postcommit.run()
            self.assertIn(('reload', 'mod_fifo'), calls)

    def test_member_change_defers_reload_to_postcommit(self):
        user = self._create_connect_user('fs_fifo_member')
        calls, patcher = self._patch_api()
        with patcher:
            fifo = self._create_fifo('Reload On Members')
            self.env.cr.postcommit.run()  # flush the create reload
            calls.clear()

            fifo.write({'member_user_ids': [Command.set([user.id])]})
            self.assertEqual(calls, [])
            self.env.cr.postcommit.run()
            self.assertIn(('reload', 'mod_fifo'), calls)

    def test_max_wait_time_change_reloads(self):
        calls, patcher = self._patch_api()
        with patcher:
            fifo = self._create_fifo('Reload On Wait')
            self.env.cr.postcommit.run()
            calls.clear()

            fifo.write({'max_wait_time': 120})
            self.env.cr.postcommit.run()
            self.assertIn(('reload', 'mod_fifo'), calls)

    def test_unrelated_field_does_not_reload(self):
        """Per-call dialplan fields are fetched fresh on every call."""
        calls, patcher = self._patch_api()
        with patcher:
            fifo = self._create_fifo('No Reload')
            self.env.cr.postcommit.run()
            calls.clear()

            fifo.write({'moh_sound': 'local_stream://moh'})
            self.env.cr.postcommit.run()
            self.assertEqual(calls, [])

    def test_unlink_defers_reload_to_postcommit(self):
        calls, patcher = self._patch_api()
        with patcher:
            fifo = self._create_fifo('Reload On Unlink')
            self.env.cr.postcommit.run()
            calls.clear()

            fifo.unlink()
            self.assertEqual(calls, [])
            self.env.cr.postcommit.run()
            self.assertIn(('reload', 'mod_fifo'), calls)

    def test_reload_deduped_per_transaction(self):
        calls, patcher = self._patch_api()
        with patcher:
            fifo1 = self._create_fifo('Dedupe 1')
            fifo2 = self._create_fifo('Dedupe 2')
            fifo1.write({'max_wait_time': 90})
            fifo2.write({'max_wait_time': 90})
            self.env.cr.postcommit.run()
            self.assertEqual(calls.count(('reload', 'mod_fifo')), 1)

    def test_later_transaction_reloads_again(self):
        """The dedupe flag must not swallow the next transaction's reload."""
        calls, patcher = self._patch_api()
        with patcher:
            fifo = self._create_fifo('Dedupe Reset')
            self.env.cr.postcommit.run()
            calls.clear()

            fifo.write({'max_wait_time': 30})
            self.env.cr.postcommit.run()
            self.assertEqual(calls.count(('reload', 'mod_fifo')), 1)

    def test_reload_failure_does_not_break_the_save(self):
        """FreeSWITCH being down must never make an Odoo save fail."""
        calls, patcher = self._patch_api(side_effect=Exception('FS is down'))
        with patcher:
            fifo = self._create_fifo('FS Down')
            self.env.cr.postcommit.run()  # must not raise
            self.assertIn(('reload', 'mod_fifo'), calls)
            self.assertTrue(fifo.exists())
