import os
import click
import json
import datetime

from contextlib import contextmanager
from dateutil import parser, relativedelta
from pathlib import Path
from ZODB import DB, FileStorage

from .timesheet_filestore import TimesheetFileStore


OTS_PATH = str(Path.home() / '.ots')
DEFAULT_FILESTORE_FILE_NAME = 'filestore.fs'


def ensure_path(path):
    if not path.exists():
        path.mkdir()


def _load_config(path=OTS_PATH):
    config_path = Path(path) / 'config.json'
    if not config_path.exists():
        return {}

    with config_path.open() as config_file:
        config = json.load(config_file)

    return config


def _save_config(config, path=OTS_PATH):
    config_path = Path(path)
    ensure_path(config_path)

    config_file_path = config_path / 'config.json'
    with config_file_path.open('w') as config_file:
        json.dump(config, config_file, indent=4)
    click.echo("Configuration saved")


def _get_database(obj):
    db = obj.get('db')
    if db is None:
        raise click.ClickException("Something went wrong, unable to find database.")
    return db


@contextmanager
def ots_filestore(obj):
    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        yield timesheet_storage


@click.group()
@click.pass_context
def cli(ctx):
    """ Simple tool to record your time usage and send it to Odoo. """

    # This is here because I haven't given the slightest thought to what
    # the file system should look like on a Windows machine.
    os_name = os.name
    if os_name != 'posix':  # TODO: This should probably just be a setting on setup.py
        raise click.ClickException(
            f"Unexpected operating system. Expected 'posix' got {os_name}."
        )

    config = _load_config()
    filestore_file_name = config.get('filestore', DEFAULT_FILESTORE_FILE_NAME)

    # Make sure the directory path for `.ots` exists.
    ots_path = Path(OTS_PATH)
    ensure_path(ots_path)

    file_storage = FileStorage.FileStorage(str(ots_path / filestore_file_name))
    db = DB(file_storage)
    with db.transaction() as connection:
        if not hasattr(connection.root, 'timesheet_storage'):
            connection.root.timesheet_storage = TimesheetFileStore()

    # Tell the context to close the database when the context tears down.
    ctx.call_on_close(db.close)

    # Database and config to context for sub commands
    ctx.ensure_object(dict)
    ctx.obj['db'] = db
    ctx.obj['config'] = config


@cli.command()
@click.pass_obj
@click.argument('task_code', default="")
@click.option('-d', 'duration',
              help="Duration of the timesheet entry in format HH:mm.")
@click.option('-m', 'description', help="Timesheet description.")
@click.option('--date', type=click.types.DateTime(formats=['%Y-%m-%d']), help="Date to add the timesheet to, if other than today.")
def add(obj, task_code, duration, description, date):
    """
    Adds a timesheet entry without starting it. Task code is the task code
    on the task in Odoo (field `code` in project.task). The task code is case
    sensitive.
    """
    if date is None:
        date = datetime.date.today()
    with ots_filestore(obj) as timesheet_storage:

        timesheet_storage.add_timesheet(
            task_code=task_code,
            description=description,
            date=date,
            duration=duration,
        )


@cli.command()
@click.pass_obj
@click.argument('task_code', required=False)
@click.option('-m', 'description', required=False)
def start(obj, task_code, description):
    """
    Start a new recording and automatically stops any running recording.

    TASK_CODE can be a Odoo task code (project.task.code) or a name of an alias.
    See ots alias --help for further information on aliases.
    """
    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.add_and_start_timesheet(task_code=task_code, description=description)


@cli.command()
@click.pass_obj
def stop(obj):
    """ Stop the currently running time recording. """
    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.stop_running()


@cli.command()
@click.pass_obj
@click.argument('index')
@click.option('-m', 'description', required=False)
@click.option('-d', 'duration',
              help="Duration of the timesheet entry in format HH:mm. Add +/- at the start to "
                   "increased/decrease the current duration instead.")
@click.option('-c', '--code', help="Task Code")
@click.option('-t', '--task_id', type=click.types.INT)
@click.option('-p', '--project_id', type=click.types.INT)
def edit(obj, index, description, duration, code, task_id, project_id):
    """
    Edit information on an existing timesheet.
    Index is the index of the timesheet as shown by the command (ots list).
    Optionally the index can be given as a combination of date offset and index
    separated by a period ".", such that the date off set marks how many days
    in the past the timesheet is. So, the index for the first timesheet for yesterday
    would be in the format "1.0" (date offset 1, index 0).
    """
    with ots_filestore(obj) as timesheet_storage:
        timesheet_edited = timesheet_storage.edit_timesheet(
            index,
            description=description,
            duration=duration,
            task_code=code,
            task_id=task_id,
            project_id=project_id,
        )
        if timesheet_edited:
            click.echo('Timesheet updated.')
        else:
            click.echo('Nothing to update.')


@cli.command()
@click.pass_obj
@click.argument('index')
@click.option('-f', '--force', is_flag=True)
def drop(obj, index, force):
    """
    Drops a timesheet.
    Index is the index of the timesheet as shown by the command (ots list).
    Optionally the index can be given as a combination of date offset and index
    separated by a period ".", such that the date off set marks how many days
    in the past the timesheet is. So, the index for the first timesheet for yesterday
    would be in the format "1.0" (date offset 1, index 0).
    """
    if not force:
        drop_confirmed = click.confirm("Confirm dropping timesheet", default=False)
        if not drop_confirmed:
            click.echo("Timesheet drop aborted.")
            return

    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.drop_timesheet(index)


@cli.command()
@click.pass_obj
def lunch(obj):
    """
    Starts a lunch timesheet. This timesheet will not be considered work time, and will not
    be synced to Odoo. This is purely for you to track your lunch if you wish. Having the lunch
    time recorded might help backtracking your work time for the day if you forget to start or stop
    a timesheet and need to do detective work.
    """
    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.add_and_start_timesheet(description="Lunch", is_worktime=False)


@cli.command()
@click.argument('index', required=False)
@click.pass_obj
def resume(obj, index):
    """
    Resume a timesheet of the given index.

    If no index is given, the previous timesheet that was running will be resumed. Also works if
    you have a currently running timesheet, in which case the currently running timesheet will
    be stopped and the previous one resumed.
    Using this command multiple times in a row will cause you to alternate between
    two timesheets.
    """
    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.resume(index)


@cli.command()
@click.argument('name', required=False)
@click.argument('task_code', required=False)
@click.option('-m', 'description')
@click.option('--project_id', type=int, help="Odoo database ID of a project.")
@click.option('--task_id', type=int, help="Odoo database ID of a task.")
@click.pass_obj
def alias(obj, name, task_code, description, project_id, task_id):
    """
    Create an alias for a timesheet. Argument "name" is the name of the Alias,
    using which you can later on create a timesheet by the alias.

    If no arguments are given, a list of existing aliases will be printed.

    Example usage:
    Creating an alias for a task you start often: `ots alias emails T8217 -m "Emails"`

    Using the alias
    ots start emails >>> Will create a timesheet with task code T8217 and description "Emails"
    """
    with ots_filestore(obj) as timesheet_storage:
        if name:
            timesheet_storage.add_alias(
                name,
                task_code=task_code,
                description=description,
                project_id=project_id,
                task_id=task_id,
            )
        else:
            timesheet_storage.print_aliases()


@cli.command()
@click.pass_obj
def sync(obj):
    """ Synchronise the timesheets with Odoo. """
    raise NotImplementedError("Not done, sry.")


@cli.command()
@click.argument('index', required=False)
@click.option('--date', type=click.types.DateTime(formats=['%Y-%m-%d']),
              help="Date to push, if not today. YYYY-MM-DD")
@click.option('-f', '--force', is_flag=True)
@click.pass_obj
def push(obj, index, date, force):
    """
    Push timesheets to Odoo. If no arguments or options are given,
    all timesheets of today will be pushed. If an index is given, only that
    one timesheet is pushed. If a date is given as an option, all timesheets
    of that one day will be pushed.
    """
    if index and date:
        click.UsageError(
            "Give an index or a date, not both. If you want to push a single timesheet, "
            "use an index. If you want to push an entire date, use a date instead.")

    if not force:
        to_be_pushed = index or date or datetime.date.today().isoformat()
        if not click.confirm(f"Push {to_be_pushed}?"):
            raise click.Abort()

    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.push(index, date)


@cli.command('search')
@click.argument('search_term')
@click.pass_obj
def search(obj, search_term):
    """
    Searches for a task in Odoo.
    If a task code is given and a perfect match is found, only that one matching
    task is shown as a result.
    Otherwise a search is done for both tasks and projects based on their
    named and the search term.
    """
    # TODO: Search a matching ID, matching code or matching name
    #  For every search prints findings separately (or in a table).
    #  If nothing was found, just print some sort of a "nothing found"
    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.odoo_search_task(search_term)


@cli.command('list')
@click.argument('days', type=int, default=1)
@click.option('--date', help="Date to print, if not today. YYYY-MM-DD")
@click.pass_obj
def list_timesheets(obj, days, date):
    """
    Lists all timesheets for a given number of days, starting from a given date.
    If date not given, defaults to today.

    DAYS: number of days to print, default 1
    """

    if date:
        date_obj = parser.parse(date).date()
    else:
        date_obj = datetime.date.today()

    with ots_filestore(obj) as timesheet_storage:
        for days in reversed(range(0, days)):
            date_to_list = date_obj - relativedelta.relativedelta(days=days)
            timesheet_storage.print_date(date_to_list)


@cli.command()
@click.pass_obj
@click.option('--database', help="Database to connect to.")
def login(obj, database):
    """
    Login to Odoo and save the session.
    The saved session will be automatically used if available when making
    any connections to Odoo.
    To remove the session, use `ots logout`
    """
    config = obj.get('config', {})

    default_hostname = config.get('odoo_hostname')
    default_username = config.get('odoo_login')
    default_ssl = config.get('ssl', True)

    hostname = click.prompt("Odoo's hostname e.g. 'mycompany.odoo.com'", default=default_hostname)
    username = click.prompt("Username", default=default_username)
    ssl = click.confirm("SSL?", default=default_ssl)

    default_port = "443" if ssl else "80"
    port = click.prompt("Port", default=default_port)

    # Password prompt without echoing the password
    password = click.prompt("Password", hide_input=True)
    config.update({
        'odoo_hostname': hostname,
        'odoo_login': username,
        'ssl': ssl,
        'odoo_port': port,
        'odoo_db': database,
    })
    _save_config(config)

    with ots_filestore(obj) as timesheet_storage:
        user_id = timesheet_storage.login(
            username,
            password,
            hostname=hostname,
            ssl=ssl,
            port=port,
            database=database,
            save=True,
        )

        click.echo(f"Successfully logged in as uid {user_id}.")


@cli.command()
@click.pass_obj
def logout(obj):
    """
    Log out of Odoo and remove the saved session.
    """
    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.logout()
        click.echo("Session removed.")


@cli.command()
@click.option('-a', '--advanced', is_flag=True,
              help="Run a full config, including more advanced options.")
@click.pass_obj
def setup(obj, advanced):
    """
    Set up basic configurations.
    """
    config = obj.get('config', {})
    # DEFAULTS
    # Database connection related values
    default_host = config.get('odoo_hostname')
    default_filestore = config.get('filestore', DEFAULT_FILESTORE_FILE_NAME)
    ssl = config.get('ssl', True)

    # Preferences
    # default_auto_sync = config.get('auto_sync')

    # Prompt for new values
    host = click.prompt("Odoo host to connect to", default=default_host)

    automatic_sync = False

    config_values = {
        'odoo_hostname': host,
        'auto_sync': automatic_sync,
    }
    if advanced:
        ssl = click.confirm("Use SSL for the connection?", default=True)
        filestore = click.prompt(
            "Name of the local filestore file that stores the Timesheets. "
            "This can be used to have several separate local databases of timesheets.",
            default=default_filestore,
        )
        if not filestore.endswith(".fs"):
            filestore = f"{filestore}.fs"

        config_values['filestore'] = filestore

    config_values['ssl'] = ssl
    config.update(config_values)
    _save_config(config)


@cli.command()
@click.argument('index')
@click.pass_obj
def update(obj, index):
    """
    Update the project/task information of a timesheet from Odoo.
    This command only updates the project name / task name of a timesheet
    based on their Task Code or project_id, this does not pull or push any
    timesheet values to/from Odoo.
    """
    with ots_filestore(obj) as timesheet_storage:
        timesheet_storage.update_timesheet_odoo_data(index)
