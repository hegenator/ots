from persistent import Persistent
from .timesheet import TimeSheet


class TimeSheetAlias(Persistent):

    def __init__(self,
                 name,
                 project_id=None,
                 task_id=None,
                 description="",
                 task_code="",
                 task_title="",
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
        self.task_title = task_title
        self.description = description

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
        return TimeSheet(
            project_id=self.project_id,
            task_id=self.task_id,
            description=self.description,
            task_code=self.task_code,
        )
