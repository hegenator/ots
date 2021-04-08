import inspect

import click
import datetime
import copy
from .helpers import format_timedelta, apply_duration_string
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

    def set_task_id(self, task_id):
        # TODO: This should probably attempt to refresh the title
        if self.task_id != task_id:
            self.task_id = task_id
            return True
        return False

    def set_project_id(self, project_id):
        # TODO: This should probably attempt to refresh the title
        if self.project_id != project_id:
            self.project_id = project_id
            return True
        return False

    def edit(self,
             description=None,
             duration=None,
             task_code=None,
             task_id=None,
             project_id=None,
             date=None,
             storage=None,
             ):
        edited = False
        update = False  # Should we update info from Odoo after edit is done
        if description is not None:
            self.description = description
            edited = True
        if duration is not None:
            if not isinstance(duration, datetime.timedelta):
                duration = apply_duration_string(duration, base_duration=self.duration)
            self.set_duration(duration)
            edited = True
        if task_code is not None:
            self.task_code = task_code
            edited = True
            update = True
        if task_id is not None:
            task_id_edited = self.set_task_id(task_id)
            edited = edited or task_id_edited
            update = True
        if project_id is not None:
            # TODO: What was the idea behind this?
            project_id_edited = self.set_project_id(project_id)
            edited = edited or project_id_edited
            update = True
        if date is not None:
            self.date = date
            edited = True

        if update and storage:
            self.update(storage)

        return edited

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
        return self.odoo_id

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
            'name': self.description,
        }

    def copy(self, **overrides):
        """
        Create a copy of this timesheet.

        :param overrides: Keyword arguments used to override the values for the
            copy.
        :return:
        """
        copy_values = {}
        init_signature = inspect.signature(TimeSheet)
        for field in init_signature.parameters:
            copy_values[field] = overrides.get(field, getattr(self, field))
        return TimeSheet(**copy_values)

    def update(self, storage):
        """
        Updates the project and task titles of a Timesheet or TimesheetAlias
        :param odoo: odoorpc.Odoo authenticated to a database
        """
        odoo = storage.load_odoo_session()

        task_code = self.task_code
        if task_code:
            task_id = storage._odoo_search_task_by_code(task_code)
            if task_id:
                task = odoo.env['project.task'].browse(task_id)
                # read returns a list, but only one task so extract the dict
                task_vals = task.read(["project_id", "name"])[0]

                self.task_id = task_vals.get("id")
                self.task_title = task_vals.get("name", "")

                # Or-guard instead of using the (None, "") as default for the `get()`
                # in case Odoo returns False as the project_id...
                project_id, project_title = task_vals.get("project_id") or (None, "")
                self.project_id = project_id
                self.project_title = project_title
        elif self.project_id:
            project = odoo.env['project.project'].browse(self.project_id)
            self.project_title = project.name

        else:
            # TODO: Later, we would like to upgrade some information on the timesheet
            #  even though we didn't have the task code, if we have task_id or project_id instead
            click.echo("Timesheet has no task code or project_id, information not updated.")

        employee_id = odoo.env['hr.employee'].search([('user_id', '=', odoo.env.uid)], limit=1)
        self.employee_id = employee_id[0] if employee_id else None
