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
            assert isinstance(project_id, int)

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
