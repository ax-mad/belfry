# belfry/app/models/request.py
from dataclasses import dataclass, field
from datetime import datetime
from entities import Priority
from croniter import croniter


@dataclass
class ReminderRequest:
    message:  str
    cron:     list[str]       = field(default_factory=list)
    begin:    datetime | None = None
    end:      datetime | None = None
    ttl:      int             = 3600
    title:    str             = ""
    tags:     list[str]       = field(default_factory=list)
    priority: Priority        = Priority.DEFAULT

    # runs after __ini__, normalize cron
    def __post_init__(self):
        if isinstance(self.cron, str):
            self.cron = [self.cron]
        
        for expr in self.cron:
            if not croniter.is_valid(expr):
                raise ValueError(f"invalid cron expression: {expr}")
