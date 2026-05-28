import asyncio, honker, os, random

db = honker.open("/data/reminders/reminders.db") 
scheduler = honker.Scheduler(db)

MESSAGES = ["Take a break", "Check logs", "Water the plants", "Weekly review", "System backup done"]
PRIORITIES = ["low", "default", "high", "urgent"]

def random_payload():
    return {
        "topic": "reminders",
        "sequence_id": "shit",
        "message": random.choice(MESSAGES),
        "title": f"Reminder #{random.randint(1, 999)}",
        "priority": random.choice(PRIORITIES),
    }

# REMINDER 1
scheduler.add(
    name="test",
    queue="reminders",
    schedule=honker.every_s(10),
    payload=random_payload()
)

# Run forever. Multiple processes can call this — only one holds
# the leader lock and actually fires.
print("RUNNING SCHEDULER")
asyncio.run(scheduler.run())
