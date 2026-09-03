from .common import ConnectProjectTestCommon


class TestRecordingLink(ConnectProjectTestCommon):

    def test_recording_inherits_task_from_call(self):
        task = self.Task.create({'name': 'T', 'partner_id': self.partner.id})
        call = self._create_call(partner=self.partner.id)
        call.task = task
        rec = self.env['connect.recording'].sudo().create({'call': call.id})
        self.assertEqual(rec.task, task)
        self.assertIn(rec, task.recorded_calls)

    def test_recording_inherits_project_from_call(self):
        project = self.Project.create({'name': 'P', 'partner_id': self.partner.id})
        call = self._create_call(partner=self.partner.id)
        call.project = project
        rec = self.env['connect.recording'].sudo().create({'call': call.id})
        self.assertEqual(rec.project, project)
        self.assertIn(rec, project.recorded_calls)

    def test_recording_without_link_stays_empty(self):
        call = self._create_call(partner=self.partner.id)
        rec = self.env['connect.recording'].sudo().create({'call': call.id})
        self.assertFalse(rec.task)
        self.assertFalse(rec.project)
