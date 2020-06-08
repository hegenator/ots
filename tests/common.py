import os
import shutil
import tempfile
from unittest import TestCase
from click.testing import CliRunner

from ots import cli


class OtsCliRunner(CliRunner):
    """
    Specialized subclass used to set and remember configuration folder settings
    so as to keep tests from messing with the usual user settings if run on a
    user's computer.
    """

    def __init__(self, cli, config_dir, *args, **kwargs):
        """
        Create a new instance

        :param cli: The root group function to be reused when using `ots_invoke`
        :param config_dir: The path to the directory that should be used to
            store the ots configurations when invoking commands using this
            runner. See original `CliRunner` for the rest of the arguments.
        """
        super().__init__(*args, **kwargs)
        self.cli = cli
        self.config_dir = config_dir

    def ots_invoke(
        self,
        args=None,
        *pargs,
        **kwargs,
    ):
        """
        Specialized form of `invoke` that automatically sets the `cli`
        parameter and gives the configuration path with every invocation.

        :param args: The arguments to invoke `ots` with. See `invoke` for details.
        :param pargs: See `invoke` for details.
        :param kwargs: See `invoke` for details.
        :return: See `invoke` for details.
        """
        ots_args = ['--config-dir', self.config_dir]
        ots_args.extend(args or [])
        return self.invoke(self.cli, ots_args, *pargs, **kwargs)


class OtsCase(TestCase):

    def setUp(self) -> None:
        super().setUpClass()
        self.orig_cwd = os.getcwd()
        self.tmp_config_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_config_dir)
        self.runner = OtsCliRunner(cli.cli, self.tmp_config_dir)

    def tearDown(self) -> None:
        os.chdir(self.orig_cwd)
        try:
            shutil.rmtree(self.tmp_config_dir)
        except (OSError, IOError):
            pass
        super().tearDownClass()
