# import os, honker, sys
from pykit.config import Configurator, env
from pykit.logging import Logger
from pykit.security import Authenticator
# from services   import Clockwork, Ringer, NtfyService
from croniter   import croniter
from fastapi    import Depends, FastAPI, HTTPException
# from models     import ReminderRequest


conf = Configurator(
    belfry_api_key=env("BELFRY_API_KEY",required=False),
    ntfy_api_key=env("NTFY_TOKEN", required=True),
    ntfy_url=env("NTFY_URL", required=True),
    database=env("BELFRY_DB",default="/data/reminders/reminders.db"), 
    queue = "reminders",
    topic = "reminders",
    worker_id = "worker-1"
)
log  = Logger(name="uvicorn", color="green")  # parameters dont seem to work as intended
auth = Authenticator(conf.belfry_api_key)
# ntfy = NtfyService(
#     conf.ntfy_url,
#     conf.ntfy_topic
# )
# scheduler = Clockwork(database=conf.database)
# worker = Ringer(
#     db_path=conf.database,
#     queue=conf.queue,
#     worker_id=conf.worker_id,
#     ntfy_service=ntfy
# )

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/reminder")
async def get_reminders():
    return {
        "reminders": [
            {"a": "reminder a"},
            {"b": "reminder b"}
        ]
    }

@app.get("/reminder/{reminder_id}")
async def get_reminder(reminder_id):
    return {reminder_id: "reminder a"}

@app.post("/reminder/{reminder_id}")
async def create_reminder(reminder_id):
    return {"success": "ok", reminder_id: "reminder a"}

@app.delete("/reminder/{reminder_id}")
async def delete_reminder(reminder_id):
    return f"deleted {reminder_id}"

### SLOP DELIMITER =====================

# Ensure data directory exists
# os.makedirs(os.path.dirname(conf.database), exist_ok=True)

# db        = honker.open(conf.database)
# scheduler = honker.Scheduler(db)

@app.post("/reminders/{reminder_id}")
async def create_or_update_reminder(reminder_id: str, body):
    """Create or update a reminder.

    A reminder IS a task registered in _honker_scheduler_tasks.
    Per schema, a second add with the same name replaces the first entirely.
    """
    if not croniter.is_valid(body.schedule):
        raise HTTPException(status_code=422, detail="Invalid cron expression")

    # [DERIVED] name from URL path per schema: "rem-<uuid>"
    name = f"rem-{reminder_id}"

    # Build the COMPLETE ntfy payload with all derived/hardcoded fields
    ntfy_payload = _build_ntfy_payload(reminder_id, body)

    # ── reminder == task ─────────────────────────────────────────────────────
    # task.name     -> "rem-{reminder_id}"   (unique per-scheduler identifier)
    # task.queue    -> "reminders"           (hardcoded, also ntfy topic)
    # task.schedule -> CronSchedule from crontab(expr)
    # task.payload  -> ntfy payload (built above — THE ENTIRE payload)
    # task.priority -> [UNUSED] default 0 (priority already in payload)
    # task.expires  -> seconds a fired job stays claimable
    scheduler.add(
        name     = name,
        queue    = QUEUE,
        # schedule = honker.crontab(body.schedule),
        payload  = ntfy_payload,
        expires  = body.expires,
    )
    log(f"POST /reminders/{reminder_id}  schedule={body.schedule}",level=10)
    log("✅ Scheduled reminder {reminder_id}")
    return {"id": reminder_id, "status": "scheduled"}


@app.put("/reminders/{reminder_id}/clear")
async def clear_reminder(reminder_id: str):
    """Pause (clear) a reminder.

    Per API reference: PUT /reminders/{reminder_id}/clear
    """
    logger.debug("PUT /reminders/%s/clear", reminder_id)
    try:
        scheduler.pause(f"rem-{reminder_id}")
    except Exception:
        raise HTTPException(status_code=404, detail="Reminder not found")
    logger.info("⏸️  Paused reminder %s", reminder_id)
    return {"id": reminder_id, "status": "paused"}


@app.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str):
    """Delete a reminder entirely.

    Per API reference: DELETE /reminders/{reminder_id}
    """
    logger.debug("DELETE /reminders/%s", reminder_id)
    try:
        scheduler.unschedule(f"rem-{reminder_id}")
    except Exception:
        raise HTTPException(status_code=404, detail="Reminder not found")
    logger.info("🗑️  Deleted reminder %s", reminder_id)
    return {"id": reminder_id, "status": "deleted"}


def _build_ntfy_payload(reminder_id: str, req) -> dict:
    """Build the COMPLETE ntfy payload per schema.

    Schema mapping:
      reminder.name     -> sequence_id  ("rem-<uuid>")
      reminder.queue    -> topic        ("reminders")
      reminder.payload  -> everything else
    """
    p = req.payload

    # [DERIVED] sequence_id from reminder.name per schema
    sequence_id = f"rem-{reminder_id}"

    return {
        "topic":       QUEUE,
        "sequence_id": sequence_id,
        "message":     p.message,
        "markdown":    True,
        "title":       p.title,
        "icon":        ICON,
        "tags":        p.tags,
        "priority":    p.priority,                  # [FROM payload] 1-5, default 3
        "attach":      p.attach,
        "click":       "",
        "actions":     [a.model_dump(exclude_none=True) for a in p.actions] if p.actions else [],
        "email":       "",
        "call":        "",
    }
