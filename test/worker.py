"""Minimal honker demo: enqueue a job, claim it, ack it."""

import asyncio, honker, time

def main():

    db = honker.open("/data/reminders/reminders.db")
    reminders_q = db.queue("reminders")

    while True:
        try:
            rem = reminders_q.claim_one("w1")
            print(f"POST REMINDER {rem.payload['sequence_id']} {rem.payload['title']} {rem.payload['message']}")
            time.sleep(1)
            rem.ack()
        except AttributeError as e:
            print("No reminders scheduled at this time")
            time.sleep(60)
            continue
        except Exception as e:
            # print(e)
            continue


if __name__ == "__main__":
    main()
