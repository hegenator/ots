from .migration_helpers import ensure_attribute


def migration_0_1(filestore):
    """
    Ensures that all timesheets in the filestore have attributes
    that were added sometime during the lifetime of 0.1 and can possibly
    be missing.
    """

    attributes = [
        ("task_title", ""),
        ("project_title", ""),
        ("odoo_id", None),
    ]
    for sheets in filestore.timesheets.values():
        for attribute, default in attributes:
            ensure_attribute(sheets, attribute, default)


__version_mig__ = ("0.1", migration_0_1)
