from typing import Optional
from pydantic import BaseModel, Field


class NtfyAction(BaseModel):
    """Ntfy action per schema docs.

    Short formats per schema:
      view:      view, <label>, <url>[, clear=true]
      broadcast: broadcast, <label>[, extras.<param>=<value>][, intent=<intent>][, clear=true]
      http:      http, <label>, <url>[, method=<method>][, headers.<header>=<value>][, body=<body>][, clear=true]
      copy:      copy, <label>, <value>[, clear=true]

    All fields from the docs are present; unused ones are None by default.
    """
    action: str = Field(..., description="Action type: view | broadcast | http | copy")
    label: str = Field(..., description="Button label shown in notification")
    url: Optional[str] = Field(default=None, description="[view/http] Target URL")
    clear: Optional[bool] = Field(default=None, description="Dismiss notification on tap")
    method: Optional[str] = Field(default=None, description="[http] HTTP method (GET, POST, …)")
    headers: Optional[dict] = Field(default=None, description="[http] headers.<header>=<value>")
    body: Optional[str] = Field(default=None, description="[http] Request body")
    value: Optional[str] = Field(default=None, description="[copy] Value to copy to clipboard")
    intent: Optional[str] = Field(default=None, description="[broadcast] Android intent string")
    extras: Optional[dict] = Field(default=None, description="[broadcast] extras.<param>=<value>")


class NtfyPayload(BaseModel):
    """Complete ntfy schema. EVERY field from the schema is present.

    Schema mapping:
      topic:       "reminders"  (hardcoded)
      sequence_id: reminder.name (derived: rem-<uuid>)
      message:     reminder.payload.message
      markdown:    true         (hardcoded)
      title:       reminder.payload.title
      icon:        hardcoded URL per schema
      tags:        reminder.payload.tags
      priority:    reminder.payload.priority (1-5, default 3)
      attach:      reminder.payload.attach
      click:       stub per schema — "include as stub but do not actually use"
      actions:     reminder.payload.actions
      email:       "test@x.alj.cx" (hardcoded)
      call:        "+1222334444"   (hardcoded)
    """
    topic: str = Field(
        default="reminders",
        description="[HARDcoded] 'reminders' per schema. Also the queue/topic name."
    )
    sequence_id: str = Field(
        ...,  # Required internally, but client does NOT send this — server derives it
        description="[DERIVED FROM reminder.name] Posted as sequence-id to ntfy. Format: rem-<uuid>. "
                    "NOT sent by client; set by server from URL path."
    )
    message: str = Field(
        ...,
        description="Notification body. Markdown is supported."
    )
    markdown: bool = Field(
        default=True,
        description="[HARDcoded] true per schema. Enables markdown rendering in ntfy."
    )
    title: Optional[str] = Field(
        default=None,
        description="Notification title. Optional per schema."
    )
    icon: str = Field(
        default="https://styles.redditmedia.com/t5_32uhe/styles/communityIcon_xnt6chtnr2j21.png",
        description="[HARDcoded] Icon URL per schema."
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Optional emoji tags shown in ntfy."
    )
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="[Constraints] Integer 1 to 5, 5 is max priority, default is 3."
    )
    attach: Optional[str] = Field(
        default=None,
        description="Optional URL to attach image/file."
    )
    click: str = Field(
        default="",
        description="[STUB] 'include as stub but do not actually use' per schema."
    )
    actions: Optional[list[NtfyAction]] = Field(
        default=None,
        description="Optional list of action buttons."
    )
    email: str = Field(
        default="test@x.alj.cx",
        description="[HARDcoded] Email address per schema."
    )
    call: str = Field(
        default="+1222334444",
        description="[HARDcoded] Phone number per schema."
    )


class NtfyPayloadRequest(BaseModel):
    """The subset of NtfyPayload that the CLIENT actually sends.

    Per schema, these are the ONLY fields that come from the client.
    All other fields (topic, sequence_id, markdown, icon, click, email, call)
    are DERIVED or HARDcoded by the server and MUST NOT be sent by the client.
    """
    message: str = Field(..., description="Notification body. Markdown supported.")
    title: Optional[str] = Field(default=None, description="Notification title.")
    priority: int = Field(default=3, ge=1, le=5, description="1-5, default 3.")
    tags: Optional[list[str]] = Field(default=None, description="Optional emoji tags.")
    attach: Optional[str] = Field(default=None, description="Optional attachment URL.")
    actions: Optional[list[NtfyAction]] = Field(default=None, description="Optional action buttons.")


class ReminderRequest(BaseModel):
    """Complete reminder schema = subset of task schema.

    A reminder IS a task registered in _honker_scheduler_tasks.
    Every field from the task/reminder schema is present, even if unused.

    Schema mapping:
      name:     "rem-uuid" — unique per-scheduler identifier, posted as sequence-id to ntfy
      queue:    "reminders" — also the topic name for ntfy
      schedule: CronSchedule from crontab(expr) or every_s(n)
      payload:  The payload for enqueued jobs = ntfy payload
      priority: Enqueue priority for fired jobs. [UNUSED] default 0.
                All reminders treated the same; priority already defined in payload.
      expires:  Seconds a fired job stays claimable. queue.sweep_expired() moves
                expired rows into _honker_dead. Default 3600.
    """
    name: Optional[str] = Field(
        default=None,
        description="[DERIVED] From URL path /reminders/{reminder_id}. Format: rem-<uuid>. "
                    "Unique per-scheduler identifier. A second add with the same name replaces "
                    "the first registration entirely (including cron expr, queue, payload)."
    )
    queue: str = Field(
        default="reminders",
        description="[HARDcoded] 'reminders' per schema. Also the topic name for ntfy."
    )
    schedule: str = Field(
        ...,
        description="Cron expression (5-field). Sent AND validated by client, "
                    "generated by LLM from natural language."
    )
    payload: NtfyPayloadRequest = Field(
        ...,
        description="The payload for enqueued jobs. Client sends NtfyPayloadRequest; "
                    "server upgrades it to full NtfyPayload by adding derived/hardcoded fields."
    )
    priority: int = Field(
        default=0,
        description="[UNUSED] For now will use default. All reminders jobs will be treated "
                    "the same; priority is already defined in payload."
    )
    expires: int = Field(
        default=3600,
        description="Seconds a fired job stays claimable. queue.sweep_expired() "
                    "moves expired rows into _honker_dead."
    )
