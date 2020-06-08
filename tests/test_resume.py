import datetime
from . import common


class TestResume(common.OtsCase):

    def test_nothing_to_resume(self):
        result = self.runner.ots_invoke(['resume'])

        self.assertIn(
            "No timesheet to resume.",
            result.output,
        )

    def test_no_such_index_to_resume(self):
        result = self.runner.ots_invoke(['resume', '1.0'])
        self.assertIn("No timesheets for date", result.output)
        self.assertIn("nothing to resume", result.output)

    def test_resume_stopped(self):
        result = self.runner.ots_invoke(['list'])
        self.assertNotIn("0.0", result.output, msg="List should be empty")
        result = self.runner.ots_invoke(['start', 'test'], catch_exceptions=False)
        self.assertIn("Timesheet started: test", result.output)
        result = self.runner.ots_invoke(['list'])
        self.assertIn("test", result.output)
        self.assertIn("(running)", result.output)
        result = self.runner.ots_invoke(['stop'])
        self.assertIn("Timesheet stopped: test", result.output)
        result = self.runner.ots_invoke(['list'])
        self.assertIn("test", result.output)
        self.assertNotIn("(running)", result.output)
        result = self.runner.ots_invoke(['resume'])
        self.assertIn("Timesheet started: test", result.output)

    def test_resume_other_day(self):
        two_days_ago = (datetime.date.today() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        test_message = 'test_two_days_ago'
        result = self.runner.ots_invoke([
            'add',
            '--date', two_days_ago,
            '-d', '01:00',
            '-m', test_message,
        ])
        self.assertEqual(result.exit_code, 0)
        result = self.runner.ots_invoke(['list'])
        self.assertNotIn(test_message, result.output)
        result = self.runner.ots_invoke(['list', '3'])
        self.assertIn(test_message, result.output)
        self.assertEqual(result.output.count(test_message), 1)
        result = self.runner.ots_invoke(['resume', '2.0'])
        self.assertIn(f"Timesheet started: {test_message}", result.output)
        result = self.runner.ots_invoke(['list', '3'])
        self.assertEqual(
            result.output.count(test_message), 2,
            msg="There should be a new, second entry with the same original "
                "description")
