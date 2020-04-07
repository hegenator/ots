import datetime
from .migration_helpers import ensure_attribute


def migration_0_2(filestore):
    """
    Migrates database initiated on version <0.2 to be compatible
    with version 0.2
    """
    # Set `date` attribute on Timesheets
    for date_ordinal, sheets in filestore.timesheets.iteritems():
        # date-attribute
        date = datetime.datetime.fromordinal(date_ordinal)
        ensure_attribute(sheets, "date", date)
    # Filestore did not have a version attribute prior to the first version
    # update.
    ensure_attribute((filestore,), "version", "0.2")


__version_mig__ = ("0.2", migration_0_2)
