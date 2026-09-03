from .common import ConnectHrTestCommon


class TestEmployeeLookup(ConnectHrTestCommon):

    def test_lookup_by_work_phone(self):
        emp = self.Employee.create({'name': 'Bob', 'work_phone': '+380671234567'})
        self.env.flush_all()
        found = self.Employee.get_employee_by_number('380671234567')
        self.assertEqual(found, emp)

    def test_lookup_by_mobile(self):
        emp = self.Employee.create({'name': 'Sue', 'mobile_phone': '+380509999999'})
        self.env.flush_all()
        self.assertEqual(self.Employee.get_employee_by_number('+380509999999'), emp)

    def test_lookup_unknown_returns_empty(self):
        self.assertFalse(self.Employee.get_employee_by_number('+380000000000'))
