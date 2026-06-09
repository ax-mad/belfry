from os import getenv

class Configurator:
    # TODO: load some shit from host

    def __int__(self):
        self.database = "/data/reminders/reminders.db"
        self.queue = "reminders"
        self.topic = "reminder"
        self.ntfy_url = getenv("NTFY_URL", "https://ntfy.alj.cx")
        self.worker_id = getenv("WORKER_ID", "worker-1")
