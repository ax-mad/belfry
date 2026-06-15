import asyncio, os, honker
from pykit import Configurator, env, Logger

# conf = Configurator(
#     database=env("BELFRY_DB",default="/data/reminders/reminders.db"), 
#     queue = "reminders",
#     topic = "reminders"
# )
# log  = Logger(name="uvicorn", color="green")  # parameters dont seem to work as intended

class Clockwork:
    def __init__(self,database:str = "/data/reminders/reminders.db"):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(database), exist_ok=True)
        self.db        = honker.open(database)
        self.scheduler = honker.Scheduler(self.db)
    
    def run(self):
        print("🚀 RUNNING SCHEDULER — waiting for leader lock...")
        asyncio.run(self.scheduler.run())
