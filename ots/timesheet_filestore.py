import click
import datetime
import odoorpc
from dateutil import relativedelta
from .helpers import format_timedelta
from persistent import Persistent
from BTrees.IOBTree import IOBTree
from BTrees.OOBTree import OOBTree
from tabulate import tabulate
from .timesheet import TimeSheet


class TimesheetFileStore(Persistent):
    """
    The "root" object that would store a bunch of Timesheet -objects.
    """

    def __init__(self):
        self.sequence_next_id = 1
        self.timesheets = IOBTree()
        self.aliases = OOBTree()  # TODO: This.

        # Specific Timesheets of interest
        self.current_running = None
        self.last_running = None

    def _get_next_id(self):
        next_id = self.sequence_next_id
        self.sequence_next_id += 1
        return next_id

    def _add_timesheet(self, timesheet, date=datetime.date.today()):
        """

        :param timesheet: Timesheet
        :param date: date to add timesheet to
        :return:
        """
        ordinal_date = date.toordinal()
        timesheets = self.timesheets.get(ordinal_date, [])

        timesheet.id = self._get_next_id()
        timesheets.append(timesheet)
        self.timesheets[ordinal_date] = timesheets

    def add_timesheet(self, task_code="", description="", is_worktime=True, date=datetime.date.today()):
        timesheet = TimeSheet(
            task_code=task_code,
            description=description,
            is_worktime=is_worktime,
        )
        self._add_timesheet(timesheet, date=date)
        return timesheet

    def add_and_start_timesheet(self, task_code="", description="", is_worktime=True):
        timesheet = self.add_timesheet(task_code=task_code, description=description, is_worktime=is_worktime)
        if self.current_running:
            self.current_running.stop()
            self.last_running = self.current_running

        self.current_running = timesheet
        timesheet.start()

    def resume(self, index=None):
        """
        :param index: index of the timesheet to resume,
        or optionally date offset and index separated by a period ('.')
        """
        if index:
            to_resume = self.get_timesheet_by_index(index)
        else:
            to_resume = self.last_running

        if not to_resume:
            click.echo("No timesheet to resume.")
        elif to_resume.is_running():
            click.echo("The timesheet to resume is already running.")
        else:
            if self.current_running:
                self.stop_running()
            else:
                self.last_running = None

            self.current_running = to_resume
            self.current_running.start()
            # TODO: We need to have some sort of logic for what happens if one resumes
            #  a timesheet from yesterday. It should start a new timesheet with the same specs,
            #  but for today.

    def stop_running(self):
        if self.current_running:
            # Making sure the `current_running` is actually running before attempting to stop it,
            # just in case we somehow stopped the timesheet but left it as `current_running`
            if self.current_running.is_running():
                self.current_running.stop()

            self.last_running = self.current_running
            self.current_running = None

    def edit_timesheet(self, index, description=None, duration=None, task_code=None, task_id=None, project_id=None):
        edited = False
        timesheet = self.get_timesheet_by_index(index)
        if description is not None:
            timesheet.description = description
            edited = True
        if duration is not None:
            timesheet.set_duration(duration)
            edited = True
        if task_code is not None:
            timesheet.task_code = task_code
            edited = True
        if task_id is not None:
            task_id_edited = timesheet.set_task_id(task_id)
            edited = edited or task_id_edited
        if project_id is not None:
            project_id_edited = timesheet.set_project_id(project_id)
            edited = edited or project_id_edited

        return edited

    @staticmethod
    def _split_index(index):
        index_error = click.UsageError(
            f"The index needs to be an integer, or two integers "
            f"separated by a period '.'. Index received: {repr(index)}"
        )

        index_split = index.split('.')
        if len(index_split) > 2:
            raise index_error
        elif len(index_split) == 1:
            try:
                date_offset = 0
                task_index = int(index_split[0].strip())
            except ValueError:
                raise index_error
        else:
            date_offset_str, task_index_str = index_split
            try:
                date_offset = int(date_offset_str.strip())
                task_index = int(task_index_str.strip())
            except ValueError:
                raise index_error

        return date_offset, task_index

    def get_timesheet_by_index(self, index):
        """
        index of a timesheet or optionally date offset and index
         separated by a period ('.')
        :param index: string
        :return: timesheet matching the index
        """
        date_offset, task_index = self._split_index(index)

        timesheet_date = datetime.date.today() - relativedelta.relativedelta(days=date_offset)
        timesheet_ordinal = timesheet_date.toordinal()
        timesheets = self.timesheets.get(timesheet_ordinal, [])
        if not timesheets:
            raise click.ClickException(
                f"No timesheets for date {str(timesheet_date)}, nothing to resume.")

        max_task_index = len(timesheets) - 1
        if task_index > max_task_index:
            raise click.ClickException(
                f"Task index out of range. Max task index for {str(timesheet_date)} is "
                f"{max_task_index}, got {task_index}.")
        timesheet = timesheets[task_index]
        return timesheet

    def find_timesheet(self, date, project_id=None, task_id=None, description=None):
        return None

    def get_timesheets(self, date_min, date_max):
        """
        Get all timesheets from the given date range (both limits inclusive)
        :param date_min: first date to include
        :param date_max: last date to include
        :return:
        """
        min_ordinal = date_min.toordinal()
        max_ordinal = date_max.toordinal()
        return self.timesheets.values(min=min_ordinal, max=max_ordinal)

    def drop_timesheet(self, index):
        date_offset, timesheet_index = self._split_index(index)
        timesheet_date = datetime.date.today() - relativedelta.relativedelta(days=date_offset)
        timesheet_ordinal = timesheet_date.toordinal()
        timesheets = self.timesheets.get(timesheet_ordinal, [])
        timesheet = timesheets.pop(timesheet_index)
        self.timesheets[timesheet_ordinal] = timesheets
        click.echo("Dropped timesheet {}".format(repr(timesheet)))

    def print_date(self, date=None):
        if date is None:
            date = datetime.date.today()

        date_ordinal = date.toordinal()
        timesheets_today = self.timesheets.get(date_ordinal, [])
        click.secho("Timesheets for {}".format(date.isoformat()), fg='green', bold=True)

        headers = ["Task Code", "Description", "Duration"]
        table = [
            [ts.task_code or "", ts.description or "", ts.get_formatted_duration(show_running=True)]
            for ts in timesheets_today]
        click.echo(tabulate(table, headers=headers, showindex='always'))

        worktime_sheets = [ts for ts in timesheets_today if ts.is_worktime]
        total_duration = self.count_total_duration(worktime_sheets)
        click.echo("Total Work Time: {}".format(format_timedelta(total_duration)))

    @staticmethod
    def count_total_duration(timesheets):
        total_duration = datetime.timedelta()
        for ts in timesheets:
            total_duration += ts.get_duration()

        return total_duration
