import click
from packaging.version import parse as version_parse
from ..__about__ import __version__ as ots_version

from .version_migrate_0_1 import __version_mig__ as mig_0_1
from .version_migrate_0_2 import __version_mig__ as mig_0_2
# Because of the nature of the filestorage OTS uses, it is possible for new
# versions to introduce new attributes to classes that don't get retroactively
# added to instances of those object stored in the database. To make sure
# the old versions of those instances function correctly when OTS version
# gets upgraded, we might need to run migrations to make the filestorage
# compatible.


# TODO: Depending on how much of these we'll get, this might need to do
#  some sort of automatic detection in the future
def get_migration_functions():
    return [
        mig_0_1,
        mig_0_2,
    ]


def check_and_migrate(filestore, auto_migrate=True):
    filestore_version = filestore.version if hasattr(filestore, 'version') else "0.0"
    if filestore_version != ots_version:
        if not auto_migrate:
            run_migration = click.confirm(
                f"Current filestore version is \"{filestore_version}\", "
                f"but your current version of OTS is \"{ots_version}\". "
                "Do you want to migrate the database?",
                default=False,
            )

            if not run_migration:
                raise click.ClickException(
                    "Migration aborted. To continue using ots, you need to either run "
                    f"the migration, or downgrade ots back to version \"{filestore_version}\"."
                )
            click.echo("Running required migrations...")
        else:
            click.echo(f"Filestore version not up-to-date with ots "
                       f"({filestore_version} < {ots_version}). "
                       f"Migrating database to current version...")

        filestore_v = version_parse(filestore_version)
        for mig_version, mig_func in get_migration_functions():
            if filestore_v < version_parse(mig_version):
                click.echo(f"Running filestore migration to version \"{mig_version}\"")
                mig_func(filestore)

        # Update the filestore's `version` to be the current one.
        # Do it here instead of in the migration function itself to avoid
        # having to always create a migration function for a new version
        # if it wouldn't otherwise require one.
        click.secho(f"Filestore migrated to version {ots_version}", fg='green', bold=True)
        filestore.version = ots_version
