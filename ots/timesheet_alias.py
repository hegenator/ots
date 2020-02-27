import click
from persistent import Persistent
from .timesheet import TimeSheet


class TimeSheetAlias(Persistent):

    def __init__(self,
                 name,
                 project_id=None,
                 task_id=None,
                 description="",
                 task_code="",
                 ):
        """
        Stuff and shit
        :param project_id:
        :param task_id:
        :param description:
        """
        self.name = name
        if project_id is not None:
            assert isinstance(project_id, int)

        if task_id is not None:
            assert isinstance(project_id, int)

        self.project_id = project_id
        self.task_id = task_id

        self.task_code = task_code
        self.description = description

        self.task_title = ""
        self.project_title = ""

        try:
            self.update()
        except:
            click.echo("Something went wrong with updating an Alias from Odoo. "
                       "As a result, you get this nice error message with no useful information "
                       "at all")

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

    def update(self):
        """
        Update the information from Odoo. Basically, try to get the task_id and project_id
        based on the task code, along with the task and project names.

        If task code not provided, but task_id or project_id have been given by the user,
        update the names based on those.
        :return:
        """
        pass

    def generate_timesheet(self):
        return TimeSheet(
            project_id=self.project_id,
            task_id=self.task_id,
            description=self.description,
            task_code=self.task_code,
        )
