import click
import datetime
import copy
from .helpers import format_timedelta
from persistent import Persistent


class TimeSheet(Persistent):
    """
    A Timesheet that tracks work time spent on a specific Odoo task or project.
    """

    def __init__(
            self,
            project_id=None,
            task_id=None,
            description="",
            task_code="",
            duration=datetime.timedelta(),
            is_worktime=True,
            date=datetime.date.today(),
    ):
        """
        Stuff and shit
        :param int project_id: Project's database ID in Odoo
        :param int task_id: Task's database ID in Odoo
        :param str description: Timesheet description
        :param datetime.timedelta: Initial tracked duration
        :param str task_code: Odoo task code (project.task.code)
        :param bool is_worktime: Whether or not the time recorded by this timesheet
        is considered work time.
        :param datetime.date date:
        """
        if project_id is not None:
            assert isinstance(project_id, int)

        if task_id is not None:
            assert isinstance(project_id, int)

        self.project_id = project_id
        self.task_id = task_id
        self.is_worktime = is_worktime

        self.task_code = task_code or ""
        self.task_title = ""
        self.project_title = ""
        self.description = description or ""

        self.start_time = None  # datetime.datetime
        self.duration = duration  # datetime.timedelta
        self.date = date
        self.created = datetime.datetime.now()

        self.employee_id = None  # Employee ID in Odoo

        # The filestore assigns a value for this once stored for the first time
        self.id = None
        self.odoo_id = None

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

    def odoo_push(self, odoo):

        timesheet_model = odoo.env['account.analytic.line']
        timesheet_vals = self._get_odoo_timesheet_vals(round_duration=True)

        # Things we don't want to push
        if not self.is_worktime:
            return

        if not self.project_id:
            click.echo(f"Timesheet {repr(self)}, no project_id. Not pushing.")
            return

        if self.odoo_id:
            odoo_timesheet = timesheet_model.browse(self.odoo_id)
            odoo_timesheet.write(timesheet_vals)
        else:
            new_id = timesheet_model.create(timesheet_vals)
            self.odoo_id = new_id
            click.echo(f"New timesheet created with id {new_id}")

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

    def _get_odoo_timesheet_vals(self, round_duration=False):
        """
        :param round_duration:
        :return:
        """

        unit_amount = self.duration.total_seconds() / 3600
        unit_amount = round(unit_amount, 2)  # Round to two decimals
        if round_duration:
            self.duration = datetime.timedelta(hours=unit_amount)

        return {
            'project_id': self.project_id,
            'task_id': self.task_id,
            'employee_id': self.employee_id,
            'unit_amount': unit_amount,
            'date': self.date.isoformat(),
        }

    def copy(self):
        # TODO: Should we just construct our own copying later? What do we gain from doing that?
        return copy.deepcopy(self)
