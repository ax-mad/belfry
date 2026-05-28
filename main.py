import os, honker, logging, sys
from croniter   import croniter
from fastapi    import Depends, FastAPI, HTTPException
from models     import ReminderRequest

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("reminder-api")

# ─── Config ───────────────────────────────────────────────────────────────────
DB_PATH  = "/data/reminders/reminders.db"
QUEUE    = "reminders"
ICON     = "https://styles.redditmedia.com/t5_32uhe/styles/communityIcon_xnt6chtnr2j21.png"

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db        = honker.open(DB_PATH)
scheduler = honker.Scheduler(db)


# ─── Optional auth (disabled for testing) ──────────────────────────────────────
TOKEN = os.getenv("BELFRY_API_TOKEN")
if TOKEN:
    from fastapi import Security
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    bearer = HTTPBearer()
    def verify_token(credentials: HTTPAuthorizationCredentials = Security(bearer)):
        if credentials.credentials != TOKEN:
            raise HTTPException(status_code=401, detail="Invalid token")
    auth_dep = [Depends(verify_token)]
    logger.info("🔒 Bearer token auth ENABLED")
else:
    auth_dep = []
    logger.info("🔓 No auth token set — running OPEN (testing mode)")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_ntfy_payload(reminder_id: str, req: ReminderRequest) -> dict:
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


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI()


@app.post("/reminders/{reminder_id}", dependencies=auth_dep)
async def create_or_update_reminder(reminder_id: str, body: ReminderRequest):
    """Create or update a reminder.

    A reminder IS a task registered in _honker_scheduler_tasks.
    Per schema, a second add with the same name replaces the first entirely.
    """
    logger.debug("POST /reminders/%s  schedule=%s", reminder_id, body.schedule)
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
        schedule = honker.crontab(body.schedule),
        payload  = ntfy_payload,
        expires  = body.expires,
    )
    logger.info("✅ Scheduled reminder %s", reminder_id)
    return {"id": reminder_id, "status": "scheduled"}


@app.put("/reminders/{reminder_id}/clear", dependencies=auth_dep)
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


@app.delete("/reminders/{reminder_id}", dependencies=auth_dep)
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


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    # Blocks terminal, outputs ALL logs (uvicorn + app)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="debug",
        reload=False,          # set True for auto-reload during dev
        access_log=True,
    )
