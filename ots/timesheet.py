import click
import datetime
import odoorpc
import copy
from .helpers import format_timedelta
from persistent import Persistent


class TimeSheet(Persistent):

    # For migration purposes. Storage might have TimeSheets that do not posses the some
    # attributes since they were created before that attribute was introduced. Such attributes
    # should be added here with a default value.
    task_title = ""
    project_title = ""

    def __init__(
            self,
            project_id=None,
            task_id=None,
            description="",
            task_code="",
            task_title="",
            project_title="",
            duration=datetime.timedelta(),
            is_worktime=True):
        """
        Stuff and shit
        :param project_id:
        :param task_id:
        :param description:
        :param is_worktime:
        """
        if project_id is not None:
            assert isinstance(project_id, int)

        if task_id is not None:
            assert isinstance(project_id, int)

        self.project_id = project_id
        self.task_id = task_id
        self.is_worktime = is_worktime

        self.task_code = task_code or ""
        self.task_title = task_title or ""
        self.project_title = project_title or ""
        self.description = description or ""

        self.start_time = None  # datetime.datetime
        self.duration = duration  # datetime.timedelta
        self.created = datetime.datetime.now()

        self.username = None  # TODO: Don't remember what I was planning on using this for...
        self.employee_id = None  # Employee ID in Odoo

        # The filestore assigns a value for this once stored for the first time
        self.id = None

    def __repr__(self):
        string_repr = ""
        if self.task_code:
            string_repr = self.task_code
        if self.description:
            if string_repr:
                string_repr += ", {}".format(self.description)
            else:
                string_repr = self.description

        return string_repr

    def start(self):
        if self.start_time:
            click.echo(f"Timesheet {repr(self)} already started.")
            return

        self.start_time = datetime.datetime.now()
        click.echo(f"Timesheet started: {repr(self)}")

    def stop(self):
        if not self.start_time:
            raise click.ClickException("Attempting to stop a timesheet that is not running.")

        start_time = self.start_time
        stop_time = datetime.datetime.now()
        previous_duration = self.duration

        current_time_delta = stop_time - start_time

        total_duration = previous_duration + current_time_delta
        self.duration = total_duration
        self.start_time = None
        click.echo(f"Timesheet stopped: {repr(self)}")

    def is_running(self):
        return bool(self.start_time)

    @staticmethod
    def odoo_search(config, task_code):

        # TODO: This has been redone elsewhere. Remove etc.
        raise NotImplementedError("Stuff")
        hostname = config.get('url')
        port = config.get('port', 8069)

        odoo = odoorpc.ODOO(host=url, port=port, protocol='jsonrpc+ssl')
        if 'project.task' not in odoo.env:
            raise click.ClickException("The target Odoo doesn't have Project Task model available.")

        task_model = odoo.env['project.task']
        task = Task.search([('code', '=', task_code)], limit=1)

        # timesheet_vals = {
        #     'project_id': 1,
        #     'task_id': 1,
        #     'employee_id': 1,
        #     'unit_amount': 0.5,
        #     'date': '2019-10-26',
        # }

        # new_timesheet = odoo.execute('account.analytic.line', 'create', timesheet_vals)
        # click.echo(message=repr(new_timesheet))

    def set_duration(self, duration):
        if self.is_running():
            raise click.ClickException("Can't edit the duration of a running timesheet. "
                                       "Stop the timesheet and try again.")

        self.duration = duration

    def get_duration(self):
        """
        Returns the total duration of this timesheet.
        If the timesheet is running, the total duration is the current recorded duration
        plus the time it has been running, so time elapsed from starting until now
        :return:
        """
        duration = self.duration
        if self.is_running():
            running_duration = datetime.datetime.now() - self.start_time
            duration += running_duration

        return duration

    def get_formatted_duration(self, show_running=False):
        formatted_duration = format_timedelta(self.get_duration())
        if show_running and self.is_running():
            formatted_duration += " (running)"
        return formatted_duration

    def copy(self):
        # TODO: Should we just construct our own copying later? What do we gain from doing that?
        return copy.deepcopy(self)
