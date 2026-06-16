# belfry/app/models/reminder.py
from dataclasses     import dataclass, field
from entities        import Recurrence
from .notification   import Notification


@dataclass
class Reminder(Recurrence):
    id:      str          = ""
    payload: Notification = None
