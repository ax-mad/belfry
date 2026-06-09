import asyncio, os, honker

# ISSUES:

# UNTESTED CODE

# LOGGING SHOULD BE INHERITED FROM MAIN (log = Logger)

# INIT FROM MAIN

# ─── Logging ──────────────────────────────────────────────────────────────────

# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
#     datefmt="%H:%M:%S",
#     handlers=[logging.StreamHandler(sys.stdout)],
# )
# logger = logging.getLogger("reminder-scheduler")

# ─── Config ───────────────────────────────────────────────────────────────────
# DB_PATH = "/data/reminders/reminders.db"


class Clockwork:
    def __init__(self,database:str = "/data/reminders/reminders.db"):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(database), exist_ok=True)
        self.db        = honker.open(database)
        self.scheduler = honker.Scheduler(self.db)
    
    def run(self):
        print("🚀 RUNNING SCHEDULER — waiting for leader lock...")
        asyncio.run(self.scheduler.run())
