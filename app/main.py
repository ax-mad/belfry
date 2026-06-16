from pykit.config import Configurator, env
from pykit.logging import Logger
from pykit.security import Authenticator
from services   import Clockwork
from fastapi    import FastAPI, HTTPException
from models     import ReminderRequest, Reminder
from entities   import Notification, NotificationAction, ActionType, Method
from croniter   import croniter


conf = Configurator(
    belfry_api_key=env("BELFRY_API_KEY",required=False),
    ntfy_token=env("NTFY_TOKEN", required=True),
    ntfy_url=env("NTFY_URL", required=True),
    database=env("BELFRY_DB",default="/data/reminders/reminders.db"), 
    queue = "reminders",
    topic = "reminders",
    worker_id = "worker-1"
)

log  = Logger(name="uvicorn", color="green")

clockwork = Clockwork(database=conf.database)
auth = Authenticator(conf.belfry_api_key)
app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/reminder")
async def get_reminders():
    return {
        "reminders": [
            {"a": "xsdf"},
            {"b": "sdfsd"}
        ]
    }

@app.get("/reminder/{reminder_id}")
async def get_reminder(reminder_id):
    return {reminder_id: Reminder()}

@app.post("/reminder/{reminder_id}")
async def create_reminder(reminder_id:str, request:ReminderRequest):

    # Validations are done post_init in ReminderRequest

    #     message:  str
    # cron:     list[str]       = field(default_factory=list)
    # begin:    datetime | None = None
    # end:      datetime | None = None
    # ttl:      int | None = None
    # title:    str             = ""
    # tags:     list[str]       = field(default_factory=list)
    # priority: Priority        = Priority.DEFAULT

    id = f"rem-{reminder_id}"
    notification = Notification(
        sequence_id=id,
        topic=conf.topic,
        title=request.title,
        message=request.message,
        tags=[f"ttl:{request.ttl}"],
        actions=[
            NotificationAction("DELETE", f"{conf.ntfy_url}/{conf.topic}/{id}", ActionType.http,
                    Method.DELETE, {"Authorization": f"Bearer {conf.ntfy_token}"})
        ]
    )

    reminder = Reminder(
        request.begin, request.end, request.ttl, request.cron, id, notification
    )

    # TODO: Pass Notification as payload to Clockwork to persist in db
    clockwork.______
    
    return {"success": "WIP", "result": notification}

@app.delete("/reminder/{reminder_id}")
async def delete_reminder(reminder_id):
    return f"deleted {reminder_id}"
