import asyncio, os, honker
from pykit.logging import log
from models import Reminder

class Clockwork:
    """
    Wrapper class for honker.Scheduler
    """
    def __init__(self, database:str):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(database), exist_ok=True)
        self.db        = honker.open(database)
        # self.queue     = honker.Queue(database, "reminders")
        self.scheduler = honker.Scheduler(self.db)
    
    def schedule(self, reminder:Reminder):
        if reminder.cron:
            self._add_periodic_task(reminder)
        else:
            self._enqueue(reminder)
    
    def _add_periodic_task(self, reminder:Reminder):
        self.scheduler.add(
            name=reminder.id,
            queue="reminders",
            schedule=reminder.cron[0],
            payload=reminder.payload,
            expires=3600
        )
        log(f"Added recurring reminder {reminder.id}")

    def _enqueue(self, reminder:Reminder):
        # self.queue.enqueue(
        #     run_at=reminder.begin.timestamp(),
        #     payload=reminder.payload
        # )
        log(f"NOT IMPLEMENTED")
    
    def run(self):
        print("🚀 RUNNING SCHEDULER — waiting for leader lock...")
        asyncio.run(self.scheduler.run())
