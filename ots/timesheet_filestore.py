import click
import datetime
import calendar
import odoorpc

from dateutil import relativedelta
from persistent import Persistent
from BTrees.IOBTree import IOBTree
from BTrees.OOBTree import OOBTree
from tabulate import tabulate

from .helpers import format_timedelta
from .timesheet import TimeSheet
from .timesheet_alias import TimeSheetAlias
from .helpers import apply_duration_string


class TimesheetFileStore(Persistent):
    """
    The "root" object that would store a bunch of Timesheets.
    """

    def __init__(self):
        self.sequence_next_id = 1
        self.timesheets = IOBTree()
        self.aliases = OOBTree()  # TODO: This.

        # Specific Timesheets of interest
        self.current_running = None
        self.last_running = None

        # Odoo connection details
        self.odoo_protocol = "jsonrpc+ssl"
        self.odoo_hostname = ""
        self.odoo_port = 8069
        self.odoo_database = ""
        self.odoo_username = ""

    def _get_next_id(self):
        next_id = self.sequence_next_id
        self.sequence_next_id += 1
        return next_id

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

    # ============================
    # ===== Timesheet stuffs =====
    # ============================

    def _add_timesheet(self, timesheet, date=datetime.date.today()):
        """

        :param timesheet: Timesheet
        :param date: date to add timesheet to
        :return:
        """
        date_ordinal = date.toordinal()
        timesheets = self.timesheets.get(date_ordinal, [])

        timesheet.id = self._get_next_id()
        timesheets.append(timesheet)
        self.timesheets[date_ordinal] = timesheets

    def add_timesheet(
            self,
            task_code="",
            description="",
            is_worktime=True,
            date=datetime.date.today(),
            duration=None):
        """

        :param task_code:
        :param description:
        :param is_worktime:
        :param date:
        :param duration:
        :return:
        """

        # Check if the task code is an alias
        if task_code and task_code in self.aliases:
            timesheet = self.aliases[task_code].generate_timesheet()
        else:
            timesheet = TimeSheet(
                task_code=task_code,
                description=description,
                is_worktime=is_worktime,
            )
        if duration is not None:
            if not isinstance(duration, datetime.timedelta):
                duration = apply_duration_string(duration)
            timesheet.set_duration(duration)

        self._add_timesheet(timesheet, date=date)
        return timesheet

    def add_and_start_timesheet(self, **kwargs):
        timesheet = self.add_timesheet(**kwargs)

        if self.current_running:
            self.current_running.stop()
            self.last_running = self.current_running

        timesheet.start()
        self.current_running = timesheet

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
            if self.current_running.is_running():
                # Making sure the `current_running` is actually running before attempting to
                # stop it, just in case we somehow stopped the timesheet but left it
                # as `current_running`
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
            if not isinstance(duration, datetime.timedelta):
                duration = apply_duration_string(duration, base_duration=timesheet.duration)
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

    def get_timesheet_by_index(self, index):
        """
        index of a timesheet or optionally negative date offset and an index
         separated by a period ('.').

        Index "2" => timesheets at index 1 for today (no offset). This is same as "0.2"
        Index "1.2" => Yesterday's (today - date offset of 1) timesheets at index 2
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
        click.echo(f"Dropped timesheet {repr(timesheet)}")

    def print_date(self, date=None):
        if date is None:
            date = datetime.date.today()

        date_ordinal = date.toordinal()
        timesheets_for_date = self.timesheets.get(date_ordinal, [])
        weekday = calendar.day_name[date.weekday()]

        headers = ["Project", "Task", "Description", "Duration"]
        table = [
            [
                ts.project_title,
                f"{ts.task_code} {ts.task_title[:50]}",
                ts.description,
                ts.get_formatted_duration(show_running=True)
            ]
            for ts in timesheets_for_date
        ]

        worktime_sheets = [ts for ts in timesheets_for_date if ts.is_worktime]
        total_duration = self.count_total_duration(worktime_sheets)

        click.secho(f"Timesheets for {date.isoformat()}, ({weekday})", fg='green', bold=True)
        click.echo(tabulate(table, headers=headers, showindex='always'))
        click.echo(f"Total Work Time: {format_timedelta(total_duration)}")

    @staticmethod
    def count_total_duration(timesheets):
        total_duration = datetime.timedelta()
        for ts in timesheets:
            total_duration += ts.get_duration()

        return total_duration

    # ============================
    # =====     Aliases     ======
    # ============================

    def add_alias(self, name, task_code="", description="", project_id=None, task_id=None):
        new_alias = TimeSheetAlias(
            name,
            task_code=task_code,
            description=description,
            project_id=project_id,
            task_id=task_id,
        )
        self.aliases[name] = new_alias
        click.echo(f"Alias {name} added.")

    def print_aliases(self, include_details=False):
        attributes = [
            ("Alias", "name"),
            ("Task Code", "task_code"),
            ("Description", "description"),
            ("Title", "task_title"),
            ("Project", "project_title"),
        ]
        details = [
            ("Project id", "project_id"),
            ("Task id", "task_id")
        ]
        if include_details:
            attributes.extend(details)

        aliases = self.aliases.values()
        headers = [a[0] for a in attributes]

        table = [
            [getattr(alias, a[1]) for a in attributes] for alias in aliases
        ]

        click.echo(tabulate(table, headers=headers))

    # ============================
    # ===== Odoo connection ======
    # ============================

    def _get_odoo_session_name(self):
        return f"ots_{self.odoo_hostname}_{self.odoo_port}_{self.odoo_protocol}_{self.odoo_database}_{self.odoo_username}"

    def set_odoo_connection_details(self, protocol, hostname, port, database, username):
        self.odoo_protocol = protocol
        self.odoo_hostname = hostname
        self.odoo_port = port
        self.odoo_database = database
        self.odoo_username = username

    def login(self, username, password, *, hostname, port=8069, ssl=True, database=None, save=True):
        """

        :param username:
        :param password:
        :param hostname:
        :param port:
        :param ssl:
        :param database:
        :param save:
        :return:
        """

        protocol = "jsonrpc+ssl" if ssl else "jsonrpc"
        odoo = odoorpc.ODOO(hostname, protocol=protocol, timeout=60, port=port, version="11.0")

        if database is None:
            click.echo("Trying to decide the database.")
            databases = odoo.db.list()
            if not databases:
                raise click.ClickException(
                    "No compatible databases found on target Odoo. "
                    "Either there are no compatible databases, or database listing is turned off. "
                    "Configure the database name if one is supposed to exist."
                )
            if len(databases) > 1:
                raise click.ClickException(
                    "More than one compatible database found on target Odoo. "
                    f"Please configure the correct database. Compatible databases: {databases}"
                )
            else:
                database = databases[0]
                click.echo(f"Attempting to connect to database {database}")

        odoo.login(database, username, password)
        user_id = odoo.env.uid

        if save:
            self.set_odoo_connection_details(
                protocol=protocol,
                hostname=hostname,
                port=port,
                database=database,
                username=username,
            )
            odoo.save(self._get_odoo_session_name())
        print(f"Employee: {employee_id}")
        return user_id

    def logout(self):
        odoorpc.ODOO.remove(self._get_odoo_session_name())

    def load_odoo_session(self):
        return odoorpc.ODOO.load(self._get_odoo_session_name())

    def is_session_stored(self):
        return self._get_odoo_session_name() in odoorpc.ODOO.list()

    def print_odoo_search_results(self, search_term):
        raise NotImplementedError()

    def _odoo_search_task_by_code(self, search_term):
        if not search_term:
            raise click.ClickException("Gief search term plz.")

        odoo = self.load_odoo_session()
        task_model = odoo.env['project.task']

        task_ids = task_model.search([('code', '=', search_term)], limit=1)
        return task_ids

    def _odoo_search_tasks_and_projects(self, search_term):
        """
        For now this is just a basic search that searches for a task or project based on a string
        :param search_term:
        :return:
        """
        # TODO: This is making a lot of assumptions atm. If we have no project installed,
        #  or if there is no code field, this'll just explode.
        if not search_term:
            raise click.ClickException("I need a search term.")

        result = {}
        odoo = self.load_odoo_session()
        task_model = odoo.env['project.task']
        project_model = odoo.env['project.project']

        # Search direct match by task code
        task_ids = self._odoo_search_task_by_code(search_term)
        project_ids = []
        if not task_ids:
            # We found no exact match, search for tasks or projects matching the search term
            task_ids = task_model.search(
                [('name', 'ilike', search_term)],
                order="project_id, code"  # TODO: Experimenting, possibly won't need customer order
            )
            project_ids = project_model.search([('name', 'ilike', search_term)])

        result['task_ids'] = task_ids
        result['project_ids'] = project_ids
        return result

    def odoo_search_task(self, search_term):
        odoo = self.load_odoo_session()
        search_results = self._odoo_search_tasks_and_projects(search_term)
        project_ids = search_results.get('project_ids', [])
        task_ids = search_results.get('task_ids', [])

        if not project_ids and not task_ids:
            click.secho("No results found.", fg='yellow', bold=True)
        else:
            click.secho(f"Search results for \"{search_term}\"", fg='green', bold=True)

        if task_ids:
            # read always returns id, even if we don't ask for it, but we use it as a header
            # so simpler to include it here and reuse the fields-list as the table headers
            task_fields = [
                "code",
                "name",
                "project_id",
                "stage_id",
                "id",
            ]
            task_vals = odoo.env['project.task'].browse(task_ids).read(task_fields)
            click.secho("Tasks:", fg='green', bold=True)
            task_headers = task_fields
            table = [
                [data[field] for field in task_headers] for data in task_vals
            ]

            click.echo(tabulate(table, headers=task_headers))
            
        if project_ids:
            project_fields = [
                "name",
                "id",
            ]
            project_vals = odoo.env['project.project'].browse(project_ids).read(project_fields)
            click.secho("Projects:", fg='green', bold=True)
            project_headers = project_fields
            table = [
                [data[field] for field in project_headers] for data in project_vals
            ]

            click.echo(tabulate(table, headers=project_headers))

    def update_timesheet_odoo_data(self, index):
        # TODO: Create a mass-update version with date-ranges or something.
        timesheet = self.get_timesheet_by_index(index)
        odoo = self.load_odoo_session()

        task_code = timesheet.task_code
        if task_code:
            task_id = self._odoo_search_task_by_code(task_code)
            if task_id:
                task = odoo.env['project.task'].browse(task_id)
                # read returns a list, but only one task so extract the dict
                task_vals = task.read(["project_id", "name"])[0]
                print(task_vals)

                timesheet.task_id = task_vals.get("id")
                timesheet.task_title = task_vals.get("name", "")

                project_id, project_title = task_vals.get("project_id", (None, ""))
                timesheet.project_id = project_id
                timesheet.project_title = project_title
        else:
            # TODO: Later, we would like to upgrade some information on the timesheet
            #  even though we didn't have the task code, if we have task_id or project_id instead
            click.echo("Timesheet has no task code, information not updated.")

        employee_id = odoo.env['hr.employee'].search([('user_id', '=', odoo.env.uid)], limit=1)
        timesheet.employee_id = employee_id[0] if employee_id else None
