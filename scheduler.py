import asyncio, os, honker, logging, sys

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("reminder-scheduler")

# ─── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "/data/reminders/reminders.db"

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

db        = honker.open(DB_PATH)
scheduler = honker.Scheduler(db)


# ─── Run forever ──────────────────────────────────────────────────────────────
# Multiple processes can call this — only one holds the leader lock and fires.
logger.info("🚀 RUNNING SCHEDULER — waiting for leader lock...")
asyncio.run(scheduler.run())
