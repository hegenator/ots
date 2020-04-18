import unittest
from click.testing import CliRunner
from ots import cli, __version__

class TestBasics(unittest.TestCase):

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli.cli, ['--version'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(
            __version__,
            result.output,
        )

