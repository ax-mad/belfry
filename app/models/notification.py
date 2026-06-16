# belfry/app/models/notification.py
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any


class ActionType(Enum):
    view      = "view"
    broadcast = "broadcast"
    http      = "http"
    copy      = "copy"


class Method(Enum):
    GET    = "GET"
    POST   = "POST"
    PUT    = "PUT"
    DELETE = "DELETE"


class Priority(IntEnum):
    MIN     = 1
    LOW     = 2
    DEFAULT = 3
    HIGH    = 4
    MAX     = 5


@dataclass
class NotificationAction:
    label:       str
    url:         str
    action_type: ActionType      = ActionType.http
    method:      Method          = Method.GET
    headers:     dict[str, str]  = field(default_factory=dict)
    body:        str             = ""
    clear:       bool            = False
    intent:      str             = ""


@dataclass
class Notification:
    id:       str
    topic:    str
    message:  str
    title:    str
    icon:     str                     = ""
    tags:     list[str]               = field(default_factory=list)
    priority: Priority                = Priority.DEFAULT
    attach:   str                     = ""
    click:    str                     = ""
    actions:  list[NotificationAction] = field(default_factory=list)
    email:    str                     = ""
    call:     str                     = ""
    delay:    Any                     = None
    time:     int | None              = None  # assigned by ntfy, never set by us
