from .common import ConnectHrTestCommon


class TestProcessEvent(ConnectHrTestCommon):

    def test_incoming_call_links_employee(self):
        """Drive the real connect.call.process_call_event() hook end-to-end
        (first-leg channel -> call creation) and assert the HR bridge's
        employee-by-caller-number auto-link runs as a side effect, rather
        than faking the link by hand."""
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        self.env.flush_all()
        channel = self._create_channel('hr-pce1', caller='+380671234567', called='+380670000001')
        with self.mock_license_check(True), self.mock_connect_reload_view():
            call_id = self.Call.process_call_event(channel)
        self.assertTrue(call_id)
        self.assertEqual(channel.call.employee, emp)

    def test_get_ref_reflects_employee(self):
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        call = self._create_call()
        call.employee = emp
        self.assertEqual(call.ref, emp)
