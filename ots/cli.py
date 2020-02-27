import os
import click
import json
import getpass
import datetime
from pathlib import Path
from dateutil import parser, relativedelta
from ZODB import DB, FileStorage

from .timesheet_filestore import TimesheetFileStore


OTS_PATH = str(Path.home() / '.ots')
DEFAULT_FILESTORE_FILE_NAME = 'filestore.fs'


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

    os_name = os.name
    if os_name != 'posix':  # TODO: This should probably just be a setting on setup.py
        raise click.ClickException(
            f"Unexpected operating system. Expected 'posix' got {os_name}."
        )

    config = _load_config()
    filestore_file_name = config.get('filestore', DEFAULT_FILESTORE_FILE_NAME)
    file_storage = FileStorage.FileStorage(str(Path(OTS_PATH) / filestore_file_name))
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
    db = _get_database(obj)
    if date is None:
        date = datetime.date.today()
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage

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
@click.option('-d', 'duration',
              help="Duration of the timesheet entry in format HH:mm. Add +/- at the start to "
                   "increased/decrease the current duration instead.")
@click.option('-c', '--code', help="Task Code")
@click.option('-t', '--task_id', type=click.types.INT)
@click.option('-p', '--project_id', type=click.types.INT)
def edit(obj, index, description, duration, code, task_id, project_id):
    db = _get_database(obj)

    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
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
    Starts a lunch timesheet. This timesheet will not be considered work time, and will not
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
@click.argument('name', required=False)
@click.argument('task_code', required=False)
@click.option('-m', 'description')
@click.option('--project_id', type=int, help="Odoo database ID of a project.")
@click.option('--task_id', type=int, help="Odoo database ID of a task.")
@click.pass_obj
def alias(obj, name, task_code, description, project_id, task_id):
    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
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


@cli.command('search')
@click.argument('search_term')
@click.pass_obj
def search(obj, search_term):
    """ Searches for a task. """
    # TODO: Search a matching ID, matching code or matching name
    #  For every search prints findings separately (or in a table).
    #  If nothing was found, just print some sort of a "nothing found"
    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        matches = timesheet_storage.odoo_search(search_term)
        click.echo(matches)


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
@click.option('--database', help="Database to connect to.")
def login(obj, database):
    db = _get_database(obj)
    config = obj.get('config', {})

    default_hostname = config.get('odoo_hostname')
    default_username = config.get('odoo_login')
    default_ssl = config.get('ssl', True)
    default_port = config.get('odoo_port', 8069)

    hostname = click.prompt("Odoo's hostname e.g. 'mycompany.odoo.com'", default=default_hostname)
    username = click.prompt("Username", default=default_username)
    ssl = click.confirm("SSL?", default=default_ssl)
    port = click.prompt("Port", default=default_port)

    # Password prompt without echoing the password
    password = click.prompt("Password", hide_input=True)
    config.update({
        'odoo_hostname': hostname,
        'odoo_login': username,
        'ssl': ssl,
        'odoo_port': port,
        'odoo_db': database
    })
    _save_config(config)

    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
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
    db = _get_database(obj)
    with db.transaction() as connection:
        timesheet_storage = connection.root.timesheet_storage
        timesheet_storage.logout()
        click.echo("Session removed.")


@cli.command()
@click.option('-a', '--advanced', is_flag=True,
              help="Run a full config, including more advanced options.")
@click.pass_obj
def setup(obj, advanced):
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
