# Odoo TimeSheets

A worktime tracker that attempts to be less shit than Awesome Timesheets.

## Getting started

### Installation
Currently supports Mac and Linux (at least most of them?). Trying to run `ots` on any other 
operating system will cause an error, by design. Since the tool has not been tested on any other 
type of system, and there is no guarantee it would work at all on, for example, Windows, and thus 
no risks are taken.


Use `pip` to install `ots`. `ots` requires Python>=3.6, so depending on your 
Python installation you probably need to use `pip3`.

### Install from Github
`pip3 install git+https://github.com/hegenator/ots`

### Install from local repository
This is currently the recommended way of installation, since as of writing this, the `master`
branch is still empty, and the repository is probably evolving quite often.

Clone the repository locally, and install from that local repository
```
git clone https://github.com/hegenator/ots.git
pip3 install ots/
```
Optionally add the  editable flag `-e` to have an easier transition from version to another
```
pip3 install -e ots/
```

## ots --help
Most of the things explained below this point can also be found using the `--help` flag. 
Certainly not all of them, but most of them probably. So if you are of the adventurous type, 
feel free to start testing and read the instructions after shit has hit the fan.

### First setup
#### ots setup
To configure preferences, the `setup` command can be used. This command also takes 
a flag `-a` to display advanced options.
Currently setup only contains two steps, one of which is behind the advanced flag.
The first configuration option is whether or not `ots` should automatically upgrade the filestore 
when a new `ots` version is detected. This is on by default.

The second option lets you define the name of the database filestorage. In regular use this 
doesn't really make much of a difference, but it allows you to practically have multiple different 
databases. This can be used for testing, or whatever else you might think of where it is useful 
to separate the timesheet data to two separate storages.
```
➜  ~ ots setup -a
Automatically migrate filestore to new version when OTS version is upgraded? [True]:
Name of the local filestore file that stores the Timesheets. This can be used to have several separate local databases of timesheets. [filestore.fs]:
Configuration saved
```

#### ots login
To configure the Odoo connection the `login` command should be used.
This asks for details about the Odoo to connect to, as well as your username and password.
```
➜  ~ ots login
Odoo's hostname e.g. 'mycompany.odoo.com' [odoo.yourcompany.com]:
Username [example.user@yourcompany.com]:
SSL? [Y/n]:
Port [443]:
Password:
Configuration saved
Trying to decide the database.
Attempting to connect to database yourcompany_database
Successfully logged in as uid 123.
```

`login` does not ask for the database, as this is not necessarily immediately known by 
regular users. If the target Odoo only has one database, `ots` will automatically choose 
the only database. If there are more than one though, you should define the correct database 
using the `--database` option.

More info:
* OTS uses the `odoorpc` (https://pypi.org/project/OdooRPC/) library to communicate with Odoo, and 
delegates the credential saving to it.
* If you wish to remove your credentials from memory, use `ots logout`. Currently this logs out 
the currently logged in credentials only. If you login to multiple different databases, hosts or 
with different usernames, only the most recently used one will be logged out.

### Usage
`ots` heavily relies on the `project.task.code` -field introduced by the `project_task_code` 
module by OCA (https://github.com/OCA/project/tree/12.0/project_task_code).

The installation of this module in your Odoo is basically mandatory, since without it 
the usage will be rather more laborious than required and you probably have better options 
for time tracking.

#### Command: start
The most basic commands to use are `start`, `list` and `stop`, which are pretty much self explanatory.

`start` takes one argument, task code, and starts a new Timesheet with that Task Code.
The most common option to give to `start` is the Timesheet description. This is done using 
the option `-m` (-m because of the influence of `git`, and because the `-d` option is used to mean `--duration` 
in some other commands and we don't want the option here to be inconsistent with the usage elsewhere.)
```
➜  ~ ots start T1234 -m "Reading the spec"
Timesheet started: T1234
```

Other tips:
* `start` automatically stops any previously running timesheets, so you don't need to separately stop 
a timesheet before starting another one
* `start` can be given a Timesheet alias instead of the task code. More about aliases down below.
* `start` always starts a new Timesheet and can not be used to resume a previously created one. 
To resume an existing timesheet, the `resume` command exists.

#### Command: list
To see your current Timesheets, the `list` command can be used.
In the most common use case `list` requires no arguments, and by default prints a summary of 
the timesheets for the current day.
```
➜  ~ ots list
Timesheets for 2020-04-07, (Tuesday)
    Project    Task    Description        Duration
--  ---------  ------  ----------------   ---------------
0              T1234   Reading the spec   00:00 (running)
Total Work Time: 00:00
```

If your `ots` has been logged in to a Odoo database, it will attempt to fetch information 
about the task based on the given task code. The fetch updates the task and project IDs 
and the names of the project and the task, which provides a more user friendly output so you 
don't have to memorise the task codes.

```
➜  ~ ots list
Timesheets for 2020-04-07, (Tuesday)
    Project                Task                      Description       Duration
--  ---------------------  ------------------------  ----------------  ---------------
0   Internal Development   T1234 Uncrash production  Reading the spec  00:00 (running)
Total Work Time: 00:00
```

Tips:
* `list` can be given a date to print using the `--date` option.
* `list` can be given an argument, DAYS, which expects an integer, to print a given amount of days. 
The listing is inclusive, and starts by default from today, but also takes the `--date` option into consideration.
* A red color on the duration indicates the timesheet has not been pushed to Odoo. Once pushed, the color 
turns to green. For Timesheets that are not meant to be pushed (see `ots lunch --help`), the colour remains 
white.
* The left-most column without a header text is the index of the timesheets that can be used 
to reference specific timesheets with other commands. More about the indexing system further down.

#### Command: stop
The `stop` command is pretty self explanatory. This command takes no arguments, 
and all it does is stops the currently running timesheet.

#### Command: resume
`resume` is used to restart a previously created timesheet.
 The most basic usage of `resume` is to give it no arguments. If no argument is given, `resume` 
 resumes the timesheet that was most recently stopped.  
 
 `resume` can be given an index as an argument if you wish to resume a specific timesheet that 
 is not necessarily the most recently stopped one. 
 
 Tips:
 * Similarly to `start`, `resume` stops any currently running timesheet when used.
 * As suggested by the previous point, resume can be used while you have a running timesheet. This will 
 simply resume the timesheet that was stopped before the currently running timesheet was started. Using `resume` 
 without an argument repeatedly without running other commands in between will effectively jump between two timesheets.
 
```
➜  ~ ots list
Timesheets for 2020-04-07, (Tuesday)
    Project    Task    Description    Duration
--  ---------  ------  -------------  ---------------
0              T1234   First Task     00:26 (running)
1              T2345   Another task   00:24
Total Work Time: 00:50

➜  ~ ots resume 1
Timesheet stopped: T1234, First task
Timesheet started: T2345, Another task

➜  ~ ots resume
Timesheet stopped: T2345, Another task
Timesheet started: T1234, First task
```  

#### Command: push
When you're all done for the day, you probably want to record your work time.
This obviously requires you to have successfully logged in to an Odoo database. To push your hours, 
simply use the `ots push` -command.

If push is given no arguments or options, it will push all the timesheets recorded for today.  
Alternatively it can be given an index as an argument to push a single specific timesheet, or a date 
as an option using the `--date` option to push a particular date.  
`push` will create a matching entry to Odoo for each timesheet entry you have, except:
1. Timesheets that are not tracking work time. Currently that means strictly a recording created by `ots lunch`
2. Timesheets that do not have a project_id (project_id is normally automatically filled in if a valid task code is provided)

#####Warning!
Push does not look at what Odoo contains when it pushes. This is mostly safe when you are pushing specific timesheets for the first time, 
but if you have already pushed a timesheet previously and you need to push it again, make sure there are no conflicts. OTS is not yet 
capable of warning or resolving situations where the time has been changed in Odoo, OTS will simply, without asking, overwrite the duration 
and any other information with what it thinks is the truth.

### Referencing a Timesheet using an index
Many of the commands utilize indices to reference Timesheets, for example `resume`, `edit` and `drop`.  

When handling Timesheets for the current day, this usage is pretty straight forward. However 
what if you need to reference something in the past?

In reality the indices used consist of two parts, a date offset and the index itself, which in use 
are separated by a period (`.`). An example index would be `"1.0"`.

This is example `1` is the date offset, which denotes the number of days back relative to today. 
The second part of the index is the index within that day.
So the example index `1.0` means "Yesterday's timesheet at index 0".
When only one number is provided, for example `"2"`, this number is assumed to be the index and 
the date offset is defaulted to `0` which means you can only give the index part when referencing 
timesheets of today.

To make it less of a math problem to reference timesheets further than today or yesterday, the `list` 
command prints the indices in the first column. This also takes into consideration the date offset.
```
➜  ~ ots list 2
Timesheets for 2020-04-06, (Monday)
     Project    Task    Description                       Duration
---  ---------  ------  --------------------------------  ----------
1.0             T0001   Something we worked on yesterday  07:30
Total Work Time: 00:00
Timesheets for 2020-04-07, (Tuesday)
    Project    Task    Description    Duration
--  ---------  ------  -------------  ---------------
0              T1234                  00:33 (running)
1              T2345   Another task   00:24
Total Work Time: 00:57
``` 


### Commands continued
#### ots edit, the solution to "Oops.."
`edit` can be used to edit information on existing timesheets.  
Most of the use cases are pretty easy to figure out without instructions, but editing a duration 
of a timesheet might require some clarifying examples.

To edit the duration, you have three options, which all require a different format of the duration 
input.

The basic format is `HH:mm`, so for example to set a duration of a timesheet to 1hour 15 minutes, 
you would use 
```
ots edit -d 01:15 [index]
``` 
When the duration is given as shown above, the command will overwrite the existing duration with the new one.

If you instead wish to increase the duration, you need to add a `+` prefix to the duration, and 
similarly to decrease you would add a `-` prefix.

So as an example, to increase the duration by half an hour, you would provide the duration as 
`"+00:30"` which then adds 30 minutes on top of the current duration.

Keep in mind that, especially when using the `-` prefix, you need to surround the option value with quotes 
or the duration will be interpreted as a command option and error out.

An example of "oops, I forgot to switch my tasks when boss called me over 15 minutes ago." where 
you would want to move 15 minutes duration from one task to another
```
ots edit -d "-00:15" 3  # decrease the duration of one timesheet by 15 minutes
ots edit -d "+00:15" 4  # increase another timesheet by the same amount
```

Tips:
* All duration edits require the target timesheet to be stopped.
* When moving time from one task to another, you can pretty easily get the previous command from 
your terminal's command history and just edit the duration sign and index to quickly move time from one 
timesheet to another.

### ots alias, the answer to "What to do with often recurring tasks"

To handle often recurring tasks, such as dailies, `ots` offers the `alias` command.

To create an alias, you simply provide the alias a name, and then fill in the same information you would 
when starting a timesheet.
This is especially useful if you have recurring tasks that don't actually have a task for in Odoo, and you wish 
to create timesheet entries directly on a project. This avoids having to type the `--project-id` option 
for `ots start`.
```
➜  ~ ots alias daily T1324 -m "Daily peer review"
Alias daily added.
➜  ~ ots alias coffee -m "Coffee break" --project_id=125
Alias coffee added.
```

To list existing aliases, simply call `alias` without any arguments.
```
➜  ~ ots alias
Alias    Task Code    Description        Title    Project
-------  -----------  -----------------  -------  ---------
coffee                Coffee break
daily    T1324        Daily peer review
```

To use an alias, simply provide the name of the alias in place of a task code when using 
`ots start` or `ots add`.

```
➜  ~ ots start daily
Timesheet started: T1324, Daily peer review
```

It is currently not possible to remove aliases, but you can redefine an alias already in use 
to override it with a new one.



## TODO
This is a list of known shortcoming or bugs.

* OTS does not track the possible differences of timesheets between Odoo and the local filestore
  * listing will only show (with color codes) if a timesheet has been pushed to Odoo or not. It does 
  not case if they are out of sync, or even if the timesheet no longer exists in Odoo.
  * There is no conflict detection or resolution. It is currently completely the users responsibility to 
  make sure it is safe to push the timesheets, if the user was to push timesheets that have already been pushed previously.
  * OTS does not fetch timesheets from Odoo that were added there manually.

* The displayed time seems to mostly match with what Odoo displays, but this could use some more testing.
OTS stores the durations as `datetime.timedelta` which effectively has a microsecond precision. Odoo on the other hand 
stores the duration as a float represented as hours. This behaviour will cause rounding errors, especially when 
that float value is displayed as hours and minutes. The more timesheets there are, the bigger the rounding difference between 
OTS and Odoo will become. This is mainly a visual issue only but can be confusing when comparing the amounts between 
totals shown by OTS and Odoo.
* `update` could use a combination of improvements, mostly to do with how it handles cases where task code is not given 
and it should rely on a task_id or project_id instead. It fetches less information than it in theory has access to.
* `update` is automatically run only when a timesheet is created. If a timesheet is edited, the user needs to 
manually call `ots update` for that timesheet to see the correct project and task titles.
* It is not possible to empty a field using `ots edit`. Currently the workaround to this is to create 
a new timesheet with the correct values and move the duration from the original timesheet to the new one, and then 
drop the old timesheet.
* Some output formatting issues that causes less than pretty stacks of tables, mostly when printing multiple days worth 
of timesheets with vastly different lengths in the project name, task name and description columns.
* Some commands don't offer all the possible options the filestore would allow. 
* Aliases don't fetch data from Odoo at all, yet.
* Some exception handling cases are still less than useful. `except: print("Shit hit the fan yo")`
* It should be possible to erase all login session with one command. Currently `logout` only erases the 
most recently used credentials, if saved.
* It should be possible to use OTS without saving your credentials, and instead be prompted for a password
when an action requiring the connection is given.
* There should be some kind of a backup system that is used before attempting to migrate 
the TimesheetStorage from one version to another. This shouldn't be more difficult to making a copy of the filestore file.
* The code is a mess
* The documentation is a mess
* The git history is a mess
* And probably a lot more that I'm not currently remembering.
