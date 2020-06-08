import unittest
from click.testing import CliRunner

from datetime import date

from ots import timesheet


class TestBasics(unittest.TestCase):

    def test_copy(self):
        t_sheet = timesheet.TimeSheet()
        new_date = date(2020, 6, 1)
        copy_sheet = t_sheet.copy(date=new_date)
        self.assertIsNot(t_sheet, copy_sheet)
        self.assertNotEqual(t_sheet.date, copy_sheet.date)
        self.assertEqual(copy_sheet.date, new_date)
