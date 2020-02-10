import os
import click
import json
import getpass
import datetime
from pathlib import Path
from dateutil import parser, relativedelta
from ZODB import DB, FileStorage

# TODO: Get filesheet_filestore.py working and use that instead
from .timesheet import TimesheetFileStore


OTS_PATH = str(Path.home() / '.ots')
OTS_FILESTORE_FILE_NAME = 'filestore.fs'


def _load_config(path=OTS_PATH):
    config_path = Path(path) / 'config.json'
    if not config_path.exists():
        return {}

    with config_path.open() as config_file:
        config = json.load(config_file)

    return config


def _save_config(config, path=OTS_PATH):
    config_path = Path(path)
    if not config_path.exists():
        os.makedirs(str(config_path), exist_ok=True)

    config_file_path = config_path / 'config.json'
    with config_file_path.open('w') as config_file:
        json.dump(config, config_file, indent=4)
    click.echo("Configuration saved")


def _get_database(obj):
    db = obj.get('db')
    if db is None:
        raise click.ClickException("Something went wrong, unable to find database.")
    return db


@click.group()
@click.pass_context
def cli(ctx):
    """ Simple tool to record your time usage and send it to Odoo. """

    if os.name != 'posix':  # TODO: This should probably just be a setting on setup.py
        raise click.ClickException(
            "Unexpected operating system. Expected 'posix' got {}".format(os.name))

    # TODO: Use the proper filestore
    file_storage = FileStorage.FileStorage(str(Path(OTS_PATH) / 'tempstore.fs'))
    db = DB(file_storage)
    with db.transaction() as connection:
        if not hasattr(connection.root, 'timesheet_storage'):
            connection.root.timesheet_storage = TimesheetFileStore()

    # Tell the context to close the database when the context tears down.
    ctx.call_on_close(db.close)

    # Database and config to context for sub commands
    ctx.ensure_object(dict)
    ctx.obj['db'] = db
    ctx.obj['config'] = _load_config()


@cli.command()
@click.pass_obj
@click.argument('task_code', default="")
@click.option('-d', 'duration', type=click.types.FLOAT, help="Duration of the timesheet entry in hours.")
@click.option('-m', 'description', help="Timesheet description.")
@click.option('--date', type=click.types.DateTime(), help="Date to add the timesheet to, if other than today.")
def add(obj, task_code, duration, description, date):
    # TODO: Giving duration as a float for hours is clumsy and annoying.
    db = _get_database(obj)
    if date is None:
        date = datetime.date.today()
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        timesheet = timesheet_storage.add_timesheet(task_code=task_code, description=description, date=date)
        if duration is not None:
            duration_timedelta = datetime.timedelta(hours=duration)
            timesheet.set_duration(duration_timedelta)


@cli.command()
@click.pass_obj
@click.argument('task_code', required=False)
@click.option('-m', 'description', required=False)
def start(obj, task_code, description):
    """ Start a new recording. Automatically stops any running recording. """

    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage

        timesheet_storage.add_and_start_timesheet(task_code=task_code, description=description)


@cli.command()
@click.pass_obj
def stop(obj):
    """ Stop the currently running time recording. """
    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        timesheet_storage.stop_running()


@cli.command()
@click.pass_obj
@click.argument('index')
@click.option('-m', 'description', required=False)
@click.option('-d', 'duration', help="Duration in hours.", type=click.types.FLOAT)
@click.option('-c', '--code', help="Task Code")
@click.option('-t', '--task_id', type=click.types.INT)
@click.option('-p', '--project_id', type=click.types.INT)
def edit(obj, index, description, duration, code, task_id, project_id):
    db = _get_database(obj)
    duration_timedelta = datetime.timedelta(hours=duration) if duration is not None else None

    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        timesheet_edited = timesheet_storage.edit_timesheet(
            index,
            description=description,
            duration=duration_timedelta,
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
@click.option('-f', '--force')
def drop(obj, index, force):
    db = _get_database(obj)
    if not force:
        drop_confirmed = click.confirm("Confirm dropping timesheet", default=False)
        if not drop_confirmed:
            click.echo("Timesheet drop aborted.")
            return

    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        timesheet_storage.drop_timesheet(index)


@cli.command()
@click.pass_obj
def lunch(obj):
    """
    Starts a lunch timesheet. This timesheet will not be considered workt ime, and will not
    be synced to Odoo.
    """
    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        timesheet_storage.add_and_start_timesheet(description="Lunch", is_worktime=False)


@cli.command()
@click.argument('index', required=False)
@click.pass_obj
def resume(obj, index):
    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        timesheet_storage.resume(index)


@cli.command()
@click.pass_obj
def sync(obj):
    """ Synchronise the timesheets with Odoo. """
    raise NotImplementedError("Not done, sry.")


@cli.command('task-search')
@click.pass_obj
def search(obj):
    """ Searches for a task. Not sure how it does that yet, though."""
    click.echo("This is where I would print out stuff I maybe found.")
    raise NotImplementedError("Nope")
    # TODO: Search a matching ID, matching code or matching name
    #  For every search prints findings separately (or in a table).
    #  If nothing was found, just print some sort of a "nothing found"


@cli.command('list')
@click.argument('days', type=int, default=1)
@click.option('--date', help="Date to print, if not today. YYYY-MM-DD")
@click.pass_obj
def list_timesheets(obj, days, date):
    """
    lists all timesheets for a given number of days starting from a given date.
    Defaults to just today.

    DAYS: number of days to print, default 1
    """

    db = _get_database(obj)
    if date:
        date_obj = parser.parse(date).date()
    else:
        date_obj = datetime.date.today()

    with db.transaction() as connection:
        for days in reversed(range(0, days)):
            date_to_list = date_obj - relativedelta.relativedelta(days=days)
            connection.root.timesheet_storage.print_date(date_to_list)


@cli.command()
@click.pass_obj
def setup(obj):
    config = obj.get('config', {})
    # DEFAULTS
    # Database connection related values
    default_host = config.get('host')
    default_db = config.get('db')
    default_username = config.get('username')

    # Preferences
    default_auto_sync = config.get('auto_sync')

    # Prompt for new values
    host = click.prompt("Odoo host to connect to", default=default_host)
    db = click.prompt("Database to connect to", default=default_db)
    username = click.prompt("Odoo username", default=default_username)
    # Password prompt without echoing it
    password = getpass.getpass("Odoo password (leave empty to not store)")

    automatic_sync = False
    # TODO: Check out OdooRPC save/load methods for saving sessions
    if password:
        automatic_sync = click.confirm(
            "Automatic sync? Do you want sync every time a timesheet "
            "is stopped?", default=default_auto_sync)

    # Test the values before storing them
    # click.echo("Attempting to authenticate with the provided credentials.")
    # common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
    # uid = common.authenticate(db, username, password, {})
    # click.echo("Successfully authenticated as uid {}".format(uid))
    #
    # # Check and store Odoo version.
    # version_info = common.version()
    # server_version = version_info.get('server_serie')
    # click.echo("Odoo server version {}".format(server_version))

    config.update({
        'host': host,
        'db': db,
        'username': username,
        'auto_sync': automatic_sync,
    })

    _save_config(config)
