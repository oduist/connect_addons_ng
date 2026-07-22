from .common import ConnectHrTestCommon


class TestProcessEvent(ConnectHrTestCommon):

    def test_incoming_call_links_employee(self):
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        self.env.flush_all()
        call = self._create_call(caller='+380671234567', direction='incoming')
        with self.mock_license_check(True):
            call.employee = self.Employee.get_employee_by_number(call.caller)
        self.assertEqual(call.employee, emp)

    def test_get_ref_reflects_employee(self):
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        call = self._create_call()
        call.employee = emp
        self.assertEqual(call.ref, emp)
