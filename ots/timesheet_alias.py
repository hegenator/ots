import click
from persistent import Persistent
from .timesheet import TimeSheet


class TimeSheetAlias(Persistent):
    """
    A Timesheet Alias can be used as a quick shortcut to create a commonly
    used Timesheet setup. The alias can be given a task code, description,
    project or task and then later the alias can be used to generate
    a timesheet with all those attributes without having to repeatedly
    give that information to a Timesheet.
    """

    def __init__(self,
                 name,
                 project_id=None,
                 task_id=None,
                 description="",
                 task_code="",
                 ):
        self.name = name
        if project_id is not None:
            assert isinstance(project_id, int)

        if task_id is not None:
            assert isinstance(task_id, int)

        self.project_id = project_id
        self.task_id = task_id

        self.task_code = task_code
        self.description = description

        self.task_title = ""
        self.project_title = ""

    def __repr__(self):
        string_repr = ""
        if self.task_code:
            string_repr = self.task_code
        if self.description:
            if string_repr:
                string_repr = f"{string_repr}, {self.description}"
            else:
                string_repr = self.description

        return string_repr

    def generate_timesheet(self):
        """
        Generates a new timesheet with the same attributes as this alias.
        :return: Timesheet
        """
        return TimeSheet(
            project_id=self.project_id,
            task_id=self.task_id,
            description=self.description,
            task_code=self.task_code,
        )

    def update(self, storage):
        """
        Updates the project and task titles from Odoo.
        :param odoo: odoorpc.Odoo authenticated to a database
        """
        odoo = storage.load_odoo_session()

        task_id = self.task_id
        task_code = self.task_code

        if not task_id and task_code:
            task_id = storage._odoo_search_task_by_code(task_code)

        if task_id:
            task = odoo.env['project.task'].browse(task_id)
            # read returns a list, but only one task so extract the dict
            task_vals = task.read(["project_id", "name"])[0]

            self.task_id = task_vals.get("id")
            self.task_title = task_vals.get("name", "")

            project_id, project_title = task_vals.get("project_id", (None, ""))
            self.project_id = project_id
            self.project_title = project_title
        elif self.project_id:
            project = odoo.env['project.project'].browse(self.project_id)
            self.project_title = project.name

        else:
            # TODO: Later, we would like to upgrade some information on the timesheet
            #  even though we didn't have the task code, if we have task_id or project_id instead
            click.echo("Alias has no task code or project_id, information not updated.")
