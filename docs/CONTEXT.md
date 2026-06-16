# Belfry — Design Session Context

## Role

You are a senior software developer experienced in Python and RESTful APIs. You are guiding a solo
developer through the design of a personal project. Do not write code unless explicitly requested.
Emphasize simple, self-documenting code that reads like a story. Single responsibility per
character. No enterprise abstractions, no domain layers. Simple, readable, beautiful.

---

## Project: Belfry

A personal reminder service. Three independent processes communicate exclusively through a shared
SQLite database. No inter-process calls, no shared memory.

### Processes

1. **belfry-api** (`belfry/app/main.py`) -- FastAPI app. Receives HTTP requests, validates them,
   writes scheduled tasks to the database. Nothing else.
2. **belfry-clockwork** (`belfry/app/services/clockwork.py`) -- Background service. Reads the
   scheduled tasks table and fires jobs into the queue at the right time. Uses the honker library.
3. **belfry-ringer** (`belfry/app/services/ringer.py`) -- Background service. Claims queued jobs
   and delivers notifications via ntfy.

Each process has its own systemd unit file in `belfry/srv/`.

### Infrastructure

- **honker** -- SQLite-backed scheduler/job queue library. Manages two tables:
  `_honker_scheduler_tasks` (recurring schedules) and a jobs queue.
- **ntfy** -- External push notification service. Ringer calls it.
- **Database** -- Single SQLite file at `$BELFRY_DB`, shared by all three processes.

---

## Project Structure

```
belfry/app
├── client/
├── main.py
├── models/
│   ├── requests.py       # ReminderRequest (API request body)
│   ├── reminder.py       # Reminder dataclass
│   ├── notification.py   # Notification, NotificationAction, Priority, ActionType, Method
│   └── honker.py         # HonkerTask, HonkerJob
├── pykit/                # Personal utility library (config, logging, security)
├── services/
│   ├── clockwork.py      # Honker interface + background scheduler
│   ├── ntfy.py           # Ntfy delivery interface
│   └── ringer.py         # Job consumer
└── utils/
    └── logger.py
```

---

## External Library: python-entities

A standalone personal library (separate GitHub repo: `python-entities`) containing reusable Python
dataclasses for generic real-world concepts. Pure stdlib, no dependencies. Installed as a package
dependency in Belfry.

```
python-entities/
├── entities/
│   ├── __init__.py
│   └── temporal/
│       ├── __init__.py
│       └── recurrence.py
├── README.md
├── pyproject.toml
└── tests/
```

Import style: `from entities.temporal import Recurrence`

---

## Defined Models

### `entities/temporal/recurrence.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta

@dataclass
class Recurrence:
    begin: datetime
    end: datetime
    duration: timedelta = field(default_factory=timedelta)
    cron: list[str] = field(default_factory=list)
```

**Semantics:**
- `cron` empty -- one-time event, fires once at `begin`
- `cron` non-empty -- recurring between `begin` and `end`
- `duration` defaults to zero (instantaneous event)
- `end` is None-equivalent when set to a far future date; no explicit None yet

---

### `belfry/app/models/notification.py`

```python
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
    action_type: ActionType     = ActionType.http
    method:      Method         = Method.GET
    headers:     dict[str, str] = field(default_factory=dict)
    body:        str            = ""
    clear:       bool           = False
    intent:      str            = ""          # Android broadcast only


@dataclass
class Notification:
    id:       str
    topic:    str
    message:  str
    title:    str
    icon:     str                      = ""
    tags:     list[str]                = field(default_factory=list)
    priority: Priority                 = Priority.DEFAULT
    attach:   str                      = ""
    click:    str                      = ""   # stub
    actions:  list[NotificationAction] = field(default_factory=list)
    email:    str                      = ""   # stub
    call:     str                      = ""   # stub
    delay:    Any                      = None
    time:     int | None               = None # assigned by ntfy, never set by us
```

---

### `belfry/app/models/reminder.py`

```python
from dataclasses import dataclass
from entities.temporal.recurrence import Recurrence
from .notification import Notification


@dataclass
class Reminder(Recurrence):
    id:      str          = ""    # workaround: dataclass inheritance issue, revisit
    payload: Notification = None  # workaround: dataclass inheritance issue, revisit
```

**Known issue:** Python raises `TypeError` when a dataclass with required fields inherits from one
with defaulted fields. `id` and `payload` have placeholder defaults to sidestep this. The correct
fix has been deferred.

---

### `belfry/app/models/honker.py`

```python
from dataclasses import dataclass, field


@dataclass
class HonkerTask:
    name:     str
    queue:    str
    schedule: str               # single cron expression
    payload:  dict              = field(default_factory=dict)
    expires:  int               = 3600


@dataclass
class HonkerJob:
    queue:    str
    payload:  dict = field(default_factory=dict)
    delay:    int  = 0
    priority: int  = 0
    expires:  int  = 3600
```

Both `HonkerTask` and `HonkerJob` carry `payload`. The task payload is the `Notification` dict.
The job payload is passed through from the task when the job is fired.

---

### `belfry/app/models/requests.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from .notification import Priority


@dataclass
class ReminderRequest:
    message:  str
    cron:     list[str]        = field(default_factory=list)
    begin:    datetime | None  = None
    end:      datetime | None  = None
    ttl:      timedelta | None = None
    title:    str              = ""
    tags:     list[str]        = field(default_factory=list)
    priority: Priority         = Priority.DEFAULT

    def __post_init__(self):
        if isinstance(self.cron, str):
            self.cron = [self.cron]   # normalize bare string to list
```

**Validation rule (in endpoint handler, not model):**
`begin` is required when `cron` is empty (single occurrence reminder).

---

## API Endpoints

```
GET    /health                    -- liveness check
GET    /reminder                  -- list all reminders
GET    /reminder/{reminder_id}    -- get one reminder
POST   /reminder/{reminder_id}    -- upsert reminder (create or replace)
DELETE /reminder/{reminder_id}    -- hard delete
```

No pause/clear endpoint. DELETE is the only removal operation.

### Current state of main.py (stubs)

```python
conf = Configurator(database=env("BELFRY_DB"))

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/reminder")
async def get_reminders():
    return {"reminders": []}

@app.get("/reminder/{reminder_id}")
async def get_reminder(reminder_id: str):
    return {reminder_id: "reminder a"}

@app.post("/reminder/{reminder_id}")
async def create_reminder(reminder_id: str, request: ReminderRequest):
    if not request.cron and request.begin is None:
        raise HTTPException(status_code=422, detail="begin is required for single occurrence reminders")
    return {"success": "WIP", "id": reminder_id, "request": request}

@app.delete("/reminder/{reminder_id}")
async def delete_reminder(reminder_id: str):
    return f"deleted {reminder_id}"
```

---

## Key Design Decisions

- **No Pydantic.** Pure stdlib `@dataclass` throughout. FastAPI serializes dataclasses natively.
- **No FastAPI lifespan.** Clockwork and Ringer are independent processes, not managed by the API.
- **honker task naming:** `rem-{reminder_id}`. Multiple cron entries create multiple tasks named
  `rem-{reminder_id}-0`, `rem-{reminder_id}-1`, etc.
- **ttl mapping:** `ReminderRequest.ttl` (timedelta) maps to a tag string `"ttl:VALUE_IN_MINUTES"`
  appended to `Notification.tags`. ntfy does not support extra fields; tags are the extension
  mechanism.
- **cron list:** `Recurrence.cron` is a list for compatibility with complex schedules and future
  projects. For now, only the first item is used when registering with honker.
- **topic** comes from `conf.queue`, hardcoded as `"reminders"`. Not client-configurable.
- **python-entities** is a standalone package imported as a dependency, not part of the Belfry
  source tree.

---

## Open Questions / Next Steps

1. **Clockwork's dual role:** Is `Clockwork` both a background scheduler process AND a thin
   interface used by the API to write to honker? If so, it has two responsibilities, which
   violates the single-responsibility principle. Needs resolution before implementing the service.

2. **`POST /reminder/{reminder_id}` handler:** Next milestone. Must validate the request, build a
   `Notification` and `Reminder`, translate to a `HonkerTask`, and call `scheduler.add()`. The
   `Notification.topic` source and full field mapping still need to be worked out.

3. **`Reminder` inheritance fix:** The `id` and `payload` placeholder defaults need a real
   solution.

4. **GET endpoints:** Reading back from `_honker_scheduler_tasks` and reconstructing `Reminder`
   objects. Schema: `(name, queue, cron_expr, payload, next_fire_at)`.

5. **Authentication:** `Authenticator` is instantiated in main.py but not yet wired to any
   endpoint as a dependency.
   