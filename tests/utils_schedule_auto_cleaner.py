import datetime
import os
import win32com.client

scheduler = win32com.client.Dispatch('Schedule.Service')
scheduler.Connect()
root_folder = scheduler.GetFolder('\\')
task_def = scheduler.NewTask(0)

# Constants
# Trigger Types: 0=Event, 1=Time, 2=Daily, 3=Weekly, 4=Monthly, 5=MonthlyDOW, 6=Idle, 7=Registration, 8=Boot, 9=Logon, 11=SessionStateChange
TASK_TRIGGER_TYPE = 2
# Action Types: 0=Exec, 5=COM Handler, 6=Send Email (Deprecated), 7=Show Message (Deprecated)
TASK_ACTION_TYPE = 0
# Logon Types: 0=None, 1=Password, 2=S4U (Background), 3=Interactive (Logged on), 4=Group, 5=Service Account, 6=Interactive or Password
TASK_LOGON_TYPE = 3
# Run Levels: 0=Least Privilege (LUA), 1=Highest Privilege
TASK_RUNLEVEL_TYPE = 0
# Creation Flags: 1=Validate, 2=Create, 4=Update, 6=CreateOrUpdate, 8=Disable, 16=No Principal ACE, 32=Ignore Reg Triggers
TASK_CREATION_TYPE = 6

# General
task_def.RegistrationInfo.Description = "Delete detection results scheduler."
task_def.Principal.LogonType = TASK_LOGON_TYPE
task_def.Principal.RunLevel = TASK_RUNLEVEL_TYPE

# Settings
task_def.Settings.ExecutionTimeLimit = "PT4H" # Quit if runtime >4H
task_def.Settings.Enabled = True
task_def.Settings.Compatibility = 6  # Windows 10

# Trigger
trigger = task_def.Triggers.Create(TASK_TRIGGER_TYPE)
trigger.StartBoundary = datetime.datetime.now().replace(microsecond=0).isoformat()
trigger.DaysInterval = 1
trigger.Enabled = True

# Actions
action = task_def.Actions.Create(TASK_ACTION_TYPE)

# Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))

action.Path = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
action.Arguments = f'"{os.path.join(root_dir, "scripts", "auto_cleaner.py")}" --log_dir "{root_dir}" --ini_dir "{root_dir}"'
#action.WorkingDirectory = root_dir
try:
    root_folder.RegisterTaskDefinition(
        "EVS-UI Delete Scheduler", task_def, TASK_CREATION_TYPE, None, None, TASK_LOGON_TYPE
    )
    print("Delete Scheduler: Task 'EVS-UI Delete Scheduler' scheduled successfully.")
except Exception as e:
    if '-2147024891' in str(e):
        print("Delete Scheduler: Access Denied. Please run this script as Administrator.")
    else:
        raise
