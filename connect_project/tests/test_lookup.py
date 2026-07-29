from .common import ConnectProjectTestCommon


class TestLookup(ConnectProjectTestCommon):

    def test_incoming_call_links_open_task(self):
        """Drive the real connect.call.process_call_event() hook end-to-end
        (first-leg channel -> call creation) and assert the Project bridge's
        task-by-partner auto-link runs as a side effect, rather than faking
        the link by hand."""
        project = self.Project.sudo().create({
            'name': 'Support Project', 'partner_id': self.partner.id,
        })
        open_stage = self.env['project.task.type'].sudo().create({
            'name': 'Open', 'fold': False, 'project_ids': [(4, project.id)],
        })
        task = self.Task.sudo().create({
            'name': 'Support ticket', 'partner_id': self.partner.id,
            'project_id': project.id, 'stage_id': open_stage.id,
        })
        self.env.flush_all()
        # Set the channel's partner directly: connect core's number-matching
        # (_find_partner) is exercised by the core module's own tests, not
        # here — we only need call.partner populated so the Project bridge's
        # task-by-partner lookup has something to act on.
        channel = self._create_channel(
            'project-pce1', caller=self.partner.phone, called='+380670000001',
            partner=self.partner.id,
        )
        with self.mock_license_check(True), self.mock_connect_reload_view():
            call_id = self.Call.process_call_event(channel)
        self.assertTrue(call_id)
        self.assertEqual(channel.call.partner, self.partner)
        self.assertEqual(channel.call.task, task)
        self.assertFalse(channel.call.project)

    def test_incoming_call_links_project_when_no_open_task(self):
        """When the partner has no open (non-folded stage) task, fall back
        to a project match."""
        project = self.Project.sudo().create({
            'name': 'Support Project', 'partner_id': self.partner.id,
        })
        folded_stage = self.env['project.task.type'].sudo().create({
            'name': 'Done', 'fold': True, 'project_ids': [(4, project.id)],
        })
        self.Task.sudo().create({
            'name': 'Closed ticket', 'partner_id': self.partner.id,
            'project_id': project.id, 'stage_id': folded_stage.id,
        })
        self.env.flush_all()
        channel = self._create_channel(
            'project-pce2', caller=self.partner.phone, called='+380670000001',
            partner=self.partner.id,
        )
        with self.mock_license_check(True), self.mock_connect_reload_view():
            call_id = self.Call.process_call_event(channel)
        self.assertTrue(call_id)
        self.assertEqual(channel.call.partner, self.partner)
        self.assertFalse(channel.call.task)
        self.assertEqual(channel.call.project, project)

    def test_get_ref_reflects_task(self):
        task = self.Task.sudo().create({'name': 'T', 'partner_id': self.partner.id})
        call = self._create_call()
        call.task = task
        self.assertEqual(call.ref, task)

    def test_get_ref_reflects_project_when_no_task(self):
        project = self.Project.sudo().create({'name': 'P', 'partner_id': self.partner.id})
        call = self._create_call()
        call.project = project
        self.assertEqual(call.ref, project)

    def test_create_with_connect_call_id_backlinks_call(self):
        call = self._create_call()
        task = self.Task.with_context(connect_call_id=call.id).create({
            'name': 'T', 'partner_id': self.partner.id,
        })
        self.env.flush_all()
        self.assertEqual(call.task, task)
