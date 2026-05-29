import asyncio, os, honker, logging, sys, httpx

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("reminder-worker")

# ─── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "/data/reminders/reminders.db"
QUEUE   = "reminders"
TOPIC   = "reminders" # temp
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.alj.cx")
WORKER_ID = os.getenv("WORKER_ID", "worker-1")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db    = honker.open(DB_PATH)
queue = db.queue(QUEUE)


async def send_to_ntfy(payload: dict) -> bool:
    """Send the ntfy payload to the ntfy server."""
    topic = TOPIC
    url = f"{NTFY_URL}/{topic}"

    # Build headers from payload fields per ntfy API
    headers = {}
    # if payload.get("title"):
    #     headers["Title"] = payload["title"]
    # if payload.get("priority"):
    #     headers["Priority"] = str(payload["priority"])
    # if payload.get("tags"):
    #     headers["Tags"] = ",".join(payload["tags"])
    # if payload.get("icon"):
    #     headers["Icon"] = payload["icon"]
    # if payload.get("attach"):
    #     headers["Attach"] = payload["attach"]
    # if payload.get("email"):
    #     headers["Email"] = payload["email"]
    # if payload.get("call"):
    #     headers["Call"] = payload["call"]
    # if payload.get("sequence_id"):
    #     headers["X-Sequence-ID"] = payload["sequence_id"]

#     # Actions as JSON if present
#     # actions = payload.get("actions", [])
#     # if actions:
#     #     headers["Actions"] = __import__("json").dumps(actions)
# 
#     # Markdown flag
#     # if payload.get("markdown"):
#     #     headers["Markdown"] = "yes"

    # print(os.getenv('NTFY_TOKEN'))

    headers["Authorization"] = f"Bearer {os.getenv('NTFY_TOKEN', '')}"

    message = payload.get("message", "")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, content=message, headers=headers)
            resp.raise_for_status()
            logger.info("📤 Sent to ntfy: %s -> HTTP %s", topic, resp.status_code)
            return True
    except Exception as e:
        logger.error("❌ Failed to send to ntfy: %s", e)
        return False


async def run_worker():
    """Claim jobs from the queue and send them to ntfy."""
    logger.info("🚀 WORKER %s started — listening on queue '%s'", WORKER_ID, QUEUE)

    async for job in queue.claim(WORKER_ID):
        logger.debug("📥 Claimed job %s", job.id)
        payload = job.payload

        success = await send_to_ntfy(payload)

        if success:
            job.ack()
            logger.info("✅ Job %s acked", job.id)
        else:
            # Retry with delay
            job.retry(delay_s=60, error="ntfy send failed")
            logger.warning("🔄 Job %s scheduled for retry", job.id)


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(run_worker())
