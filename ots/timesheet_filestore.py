import click
import datetime
import calendar
import odoorpc

from dateutil import relativedelta
from persistent import Persistent
from BTrees.IOBTree import IOBTree
from BTrees.OOBTree import OOBTree
from tabulate import tabulate
from collections import defaultdict

from .helpers import format_timedelta
from .timesheet import TimeSheet
from .timesheet_alias import TimeSheetAlias
from .helpers import apply_duration_string, limit_str_length
from .__about__ import __version__


class TimesheetFileStore(Persistent):
    """
    The "root" object that stores and controls Timesheets, and handles
    the Odoo connection.
    """

    def __init__(self):
        self.sequence_next_id = 1
        self.timesheets = IOBTree()
        self.aliases = OOBTree()

        # Specific Timesheets of interest
        self.current_running = None
        self.last_running = None

        # Odoo connection details
        self.odoo_protocol = "jsonrpc+ssl"
        self.odoo_hostname = ""
        self.odoo_port = 8069
        self.odoo_database = ""
        self.odoo_username = ""
        # The ots version this filestore was initiated on.
        self.version = __version__

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

        # attempt to update the timesheet, but don't explode even if it fails
        if self.is_session_stored():
            try:
                timesheet.update(self)
            except Exception as e:  # TODO: Guess
                click.secho(
                    "Something went wrong when trying to update data from Odoo.\n"
                    f"{e}",
                    fg='yellow',
                    bold=True,
                )

    def add_timesheet(
            self,
            task_code="",
            description="",
            is_worktime=True,
            date=datetime.date.today(),
            duration=None,
            task_id=None,
            project_id=None,
    ):
        """
        :param str task_code: Odoo task code
        :param str description: Timesheet description
        :param bool is_worktime: Whether or not the time tracked is work time or not
        :param datetime.date date: Date of the timesheet
        :param (datetime.timedelta, str) duration: Duration of tracked time for the timesheet
        :param int task_id: Odoo database id of the task
        :param int project_id: Odoo database id of the project
        :return Timesheet: Return created timesheet
        """

        # Check if the task code is an alias
        if task_code and task_code in self.aliases:
            timesheet = self.aliases[task_code].generate_timesheet()
            edit_vals = {}
            if description:
                edit_vals['description'] = description
            if date != datetime.date.today():
                edit_vals['date'] = date
            if edit_vals:
                timesheet.edit(**edit_vals)
        else:
            timesheet = TimeSheet(
                task_code=task_code,
                description=description,
                is_worktime=is_worktime,
                date=date,
                task_id=task_id,
                project_id=project_id,
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

            today = datetime.date.today()
            # TODO: allow the user to configure that they want a new timesheet
            #  on the same day if the resumed timesheet has been pushed to Odoo?
            if to_resume.date != today:
                # Resuming on a different day: start a new timesheet with the
                # same details
                new_timesheet = to_resume.copy(
                    date=today,
                    duration=datetime.timedelta(),
                )
                self._add_timesheet(new_timesheet)
                self.current_running = new_timesheet
            else:
                # Still the same day: we can continue the same timesheet
                self.current_running = to_resume
            self.current_running.start()

    def stop_running(self):
        if self.current_running:
            if self.current_running.is_running():
                # Making sure the `current_running` is actually running before attempting to
                # stop it, just in case we somehow stopped the timesheet but left it
                # as `current_running`
                self.current_running.stop()

            self.last_running = self.current_running
            self.current_running = None

    def edit_timesheet(self, index, **kwargs):
        timesheet = self.get_timesheet_by_index(index)
        return timesheet.edit(storage=self, **kwargs)

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
        ordinal_today = datetime.date.today().toordinal()
        if date is None:
            date_ordinal = ordinal_today
        else:
            date_ordinal = date.toordinal()
        date_offset = ordinal_today - date_ordinal

        timesheets_for_date = self.timesheets.get(date_ordinal, [])
        weekday = calendar.day_name[date.weekday()]

        headers = ["Project", "Task", "Description", "Duration"]

        def get_coloured_duration(ts):
            dur = ts.get_formatted_duration(show_running=True)
            if ts.is_worktime:
                # TODO: This doesn't care if the time has changed since last
                #  push, so green is not always a sign of "good status"
                colour = "green" if ts.odoo_id else "red"
                dur = click.style(dur, fg=colour)
            return dur

        # Table containing the actual data
        table = [
            [
                limit_str_length(ts.project_title),
                limit_str_length(f"{ts.task_code} {ts.task_title}"),
                limit_str_length(ts.description),
                get_coloured_duration(ts)
            ]
            for ts in timesheets_for_date
        ]
        # Generate values for the index column. This adds the date offset for
        # dates other than today.
        no_indices = len(table)
        index_prefix = str(date_offset) if date_offset else ""
        indices = [f"{index_prefix}.{i}" if index_prefix else str(i) for i in range(no_indices)]

        # Total work time
        worktime_sheets = [ts for ts in timesheets_for_date if ts.is_worktime]
        total_duration = self.count_total_duration(worktime_sheets)

        # We want to disable tabulate's number parsing on the index column
        # because it changes '4.0' to '4', which is not desired.
        # But tabulate doesn't handle this option well if the column is empty,
        # so we need to only disable it when we actually have something in
        # the column.
        disable_numparse = [0] if indices else False

        click.secho(f"Timesheets for {date.isoformat()}, ({weekday})", fg='green', bold=True)
        click.echo(
            tabulate(
                table,
                headers=headers,
                showindex=indices,
                disable_numparse=disable_numparse,
            )
        )
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
    def _get_alias(self, name):
        try:
            alias = self.aliases[name]
        except KeyError:
            raise click.ClickException(f"Alias {name} does not exist.")
        return alias

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
        if self.is_session_stored():
            try:
                new_alias.update(self)
            except Exception as e:  # TODO: Guess
                click.secho(
                    "Something went wrong when trying to update data from Odoo.\n"
                    f"{e}",
                    fg='yellow',
                    bold=True,
                )

    def delete_alias(self, name):
        try:
            self.aliases.pop(name)
        except KeyError:
            raise click.UsageError(f"Alias {name} doesn't exist, "
                                   "and thus can't be deleted.")

        click.echo(f"Alias {name} deleted.")

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
            [limit_str_length(getattr(alias, a[1])) for a in attributes] for alias in aliases
        ]

        click.echo(tabulate(table, headers=headers))

    def update_alias(self, name):
        """
        Update an alias from Odoo. If no name is given, update all aliases.
        :param str name: name of an alias, or None to update all aliases
        """
        if self.is_session_stored():
            if name is not None:
                aliases = [self._get_alias(name)]
            else:
                aliases = self.aliases.values()

            try:
                with click.progressbar(aliases) as alias_bar:
                    for alias in alias_bar:
                        alias.update(self)
            except Exception as e:  # TODO: Guess
                click.secho(
                    "Something went wrong when trying to update data from Odoo.\n"
                    f"{e}",
                    fg='yellow',
                    bold=True,
                )
        else:
            raise click.ClickException("Odoo session not available. To update data from Odoo, "
                                       "please log in with 'ots login'.")

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

    def login(self, username, password, *, hostname, port=443, ssl=True, database=None, save=True):
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
        odoo = odoorpc.ODOO(hostname, protocol=protocol, timeout=60, port=port)

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
        return user_id

    def logout(self):
        odoorpc.ODOO.remove(self._get_odoo_session_name())

    def load_odoo_session(self):
        return odoorpc.ODOO.load(self._get_odoo_session_name())

    def is_session_stored(self):
        return self._get_odoo_session_name() in odoorpc.ODOO.list()

    def push(self, index, date):
        created = []
        wrote = []
        if index:
            timesheets = [self.get_timesheet_by_index(index)]
        else:
            if not date:
                date = datetime.date.today()

            date_ordinal = date.toordinal()
            timesheets = self.timesheets.get(date_ordinal, [])

        odoo = self.load_odoo_session()
        with click.progressbar(timesheets) as timesheet_bar:
            for timesheet in timesheet_bar:
                odoo_id = timesheet.odoo_id
                new_id = timesheet.odoo_push(odoo)
                if odoo_id:
                    wrote.append(str(odoo_id))
                elif new_id:
                    created.append(str(new_id))

        if created:
            click.echo(f"New timesheets created with ids: {', '.join(created)}")
        if wrote:
            click.echo(f"Wrote possible changes to existing timesheets: {', '.join(wrote)}")

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
                order="project_id, id desc"  # TODO: Experimenting, possibly won't need custom order
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
            return
        else:
            click.secho(f"Search results for \"{search_term}\"", fg='green', bold=True)

        result_strings = []
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
            table = [
                [
                    limit_str_length(data[field]) for field in task_fields
                ]
                for data in task_vals
            ]
            ttitle = click.style("Tasks:", fg='green', bold=True)
            ttable = tabulate(table, headers=task_fields)
            task_result = f"{ttitle}\n{ttable}"
            result_strings.append(task_result)

        if project_ids:
            project_fields = [
                "name",
                "id",
            ]
            project_vals = odoo.env['project.project'].browse(project_ids).read(project_fields)

            table = [
                [limit_str_length(data[field]) for field in project_fields] for data in project_vals
            ]
            ptitle = click.style("Projects:", fg='green', bold=True)
            ptable = tabulate(table, headers=project_fields)
            project_result = f"{ptitle}\n{ptable}"
            result_strings.append(project_result)

        if result_strings:
            click.echo("\n\n".join(result_strings))

    def update_timesheet_odoo_data(self, index):
        timesheet = self.get_timesheet_by_index(index)
        # TODO: Create a mass-update version with date-ranges or something.
        timesheet.update(self)
