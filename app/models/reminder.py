# belfry/app/models/reminder.py
from dataclasses     import dataclass
from entities        import Recurrence, Notification


@dataclass
class Reminder(Recurrence):
    id:      str          = ""
    payload: Notification = None
