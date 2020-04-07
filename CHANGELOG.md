# Changelog

## 0.2
* Added a changelog file
* Updated README with some basic instructions
* Ensure that the default ots directly `~~.ots` actually exists before trying to use it.
* Added a mechanism for database migrations between versions
* Added migration functions for version things that happened during 0.1, and for version 0.2
* TimesheetStorage now knows which version of `ots` it was created on, or migrated to. This is used to determine 
if any migration functions need to be run.
* As a result of the version related changes, a new dependency `packaging` was added to the `setup.py`
* Added a setup option to choose between automatic and manual migrations. When a new `ots` version is detected, 
depending on this option's value, `ots` will either prompt for confirmation or automatically run the migration functions 
for the new version, if any exist. Because of the way the database is stored, older version of the TimesheetStorage or the timesheets 
will not automatically acquire attributes that might have been defined for the class in newer versions, so the migration functions 
are used to make sure the TimesheetStorage and all the timesheets have these new attributes defined to avoid exceptions caused not having them.
* Removed the setup options for default hostname and SSL. These are asked during the login anyway, and running the setup would not 
remove the need to run `login`, so it was pointless to have them in two separate places.
* The indices displayed by `list` now display the date offset part of the index for previous days.
* Renamed the `--project_id` option to `--project-id`, because I find it nicer.
* `add` and `start` now offer the `--project-id` and `--task-id` options previously only available on the `edit` and `alias` commands.
* Added a `date` field to Timesheets. Previously the date of the timesheet was only known by the TimesheetStorage, which caused problems 
during the timesheet push, since the Timesheets do the pushing to Odoo themselves, and without the date field they were using the creation date 
instead as the date that was sent to Odoo. This caused problems when pushing timesheets to Odoo that were manually added to the past.
* Added an empty row between task and project search results if matches were found from both.
* Providing a description with `-m` when using `start` or `add` with an alias now overrides the description defined on the alias 
instead of silently discarding the description provided by the user. 
