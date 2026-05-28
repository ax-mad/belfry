
# Honker Usage

## Quick Start

honker is a SQLite extension + language bindings that add Postgres-style NOTIFY/LISTEN semantics to SQLite, with built-in durable pub/sub, task queue, and event streams, without client polling or a daemon/broker. Any language that can SELECT load_extension('honker') gets the same features.

honker works by replacing application-level polling with a single-digit-µs PRAGMA data_version read on the database every 1ms, achieving push-like semantics and cross-process notifications with single-digit-millisecond delivery.

Some bindings expose experimental watcher backends, such as mmap of <db>-shm in WAL mode or kernel file events. AUTO backend modes stay conservative and use PRAGMA data_version. The stable semantics stay the same: wake on committed updates, ignore rolled-back work, and re-read SQLite state after every wake.

Alpha software. Better than experimental but not beta-quality yet.

SQLite is increasingly the database for shipped projects. Those inevitably require pubsub and a task queue. The usual answer is "add Redis + Celery." That works, but it introduces a second datastore with its own backup story, a dual-write problem between your business table and the queue, and the operational overhead of running a broker.

honker takes the approach that if SQLite is the primary datastore, the queue should live in the same file. That means INSERT INTO orders and queue.enqueue(...) commit in the same transaction. Rollback drops both. The queue is just rows in a table with a partial index.

Prior art: pg_notify (fast triggers, no retry/visibility), Huey (SQLite-backed Python), pg-boss and Oban (the Postgres-side gold standards we're chasing on SQLite). If you already run Postgres, use those, as they are excellent.

honker ships as a Rust crate (honker, plus honker-core/honker-extension), a SQLite loadable extension, and language packages: Python (honker), Node (@russellthehippo/honker-node), Bun (@russellthehippo/honker-bun), Ruby (honker), Go, Elixir, C++, .NET / C#, and JVM / Kotlin packages. The on-disk layout is defined once in Rust; every binding is a thin wrapper around the loadable extension.

See Binding support for the current truth table: which bindings have typed queue/stream/listen/scheduler APIs, which ones have packaged-install proof, and what CI actually proves.

At a glance
import honker

db = honker.open("app.db")
emails = db.queue("emails")

## Your first queue
Open a database, create a queue, enqueue a job, and claim it, all in one script.

Python
Node
Rust
Go
Ruby
Bun
Elixir
.NET
Java
Kotlin
C++
SQL
import honker

db = honker.open("app.db")        # opens or creates the file
q = db.queue("greetings")

q.enqueue({"name": "world"})

job = q.claim_one("worker-1")
print(f"hello, {job.payload['name']}!")
job.ack()

A proper worker
The worker loop wakes within 1-2 ms when a new job lands, via a shared 1 ms PRAGMA data_version poll on the database. No application-level polling. (Two experimental alternatives — kernel filesystem events and mmap’d WAL-index reads — are available behind opt-in flags; see Watcher backends.)

Python
Rust
Go
Ruby
Bun
Elixir
.NET
Java
Kotlin
C++
SQL
import asyncio
import honker

async def main():
    db = honker.open("app.db")
    q = db.queue("emails")

    async for job in q.claim("worker-1"):
        try:
            await send_email(job.payload)
            job.ack()
        except Exception as e:
            # Scheduled retry with backoff. After max_attempts (default 3),
            # the job moves to _honker_dead with last_error set.
            job.retry(delay_s=60, error=str(e))

asyncio.run(main())

Atomic enqueue with business writes
The killer feature of a SQLite-native queue: the enqueue lands in the same transaction as your business write. No dual-write problem, no outbox pattern to bolt on (though Honker has one for external systems).

Python
Node
Rust
Go
Ruby
Bun
Elixir
.NET
Java
Kotlin
C++
SQL
with db.transaction() as tx:
    tx.execute(
        "INSERT INTO orders (id, total, customer_id) VALUES (?, ?, ?)",
        [42, 9900, "alice"],
    )
    q.enqueue({"order_id": 42, "email_type": "confirmation"}, tx=tx)
    # One COMMIT. Either both land or neither does.

What’s next
Queues for priority, delays, retries, dead-letter
Tasks for Huey-style @task decorators (Python)
Streams for durable pub/sub with per-consumer offsets
Pub/Sub for pg_notify-style ephemeral signals
Scheduler for cron and @every time-trigger tasks

### Enqueue
emails.enqueue({"to": "alice@example.com"})

### Consume (worker process)
async for job in emails.claim("worker-1"):
    send(job.payload)
    job.ack()
Any enqueue can be atomic with a business write. Rollback drops both.

with db.transaction() as tx:
    tx.execute("INSERT INTO orders (user_id) VALUES (?)", [42])
    emails.enqueue({"to": "alice@example.com"}, tx=tx)
Features
Today:

Notify/listen across processes on one .db file
Work queues with retries, priority, delayed jobs, and a dead-letter table
Any send can be atomic with your business write (commit together or roll back together)
Single-digit millisecond cross-process reaction time, no polling
Handler timeouts, declarative retries with exponential backoff
Delayed jobs, task expiration, named locks, rate-limiting
Time-trigger scheduling with a leader-elected scheduler: 5-field cron, 6-field cron, and @every <n><unit>. Schedules are addressable rows you can pause, resume, update, list, and unschedule from any process or binding.
Cancel a pending or in-flight job by id (queue.cancel(id)); read any job's row via queue.get_job(id).
Opt-in task result storage (enqueue returns an id, worker persists the return value, caller awaits queue.wait_result(id))
Durable streams with per-consumer offsets and configurable flush interval
SQLite loadable extension so any SQLite client can read the same tables
Bindings: Python, Node.js, Rust, Go, Ruby, Bun, Elixir, .NET / C#, Java/JVM, and Kotlin
Works inside an ORM-owned SQLite connection. SQLAlchemy, SQLModel, Django, Drizzle, Kysely, sqlx, GORM, ActiveRecord, Ecto, Hibernate, jOOQ, MyBatis, Exposed (guide)
Deliberately not built: task pipelines/chains/groups/chords, multi-writer replication, workflow orchestration with DAGs.

Quick start
Python: queue (durable at-least-once work)
pip install honker
import honker
db = honker.open("app.db")
emails = db.queue("emails")

with db.transaction() as tx:
    tx.execute("INSERT INTO orders (user_id) VALUES (?)", [42])
    emails.enqueue({"to": "alice@example.com"}, tx=tx)   # atomic with order

# Then in a worker, do: 
async for job in emails.claim("worker-1"):               # wakes on updates or due deadlines
    try:
        send(job.payload); job.ack()
    except Exception as e:
        job.retry(delay_s=60, error=str(e))
claim() is an async iterator. Each iteration is one claim_batch(worker_id, 1). Wakes on any database update, or when the next claim-relevant deadline arrives (run_at for delayed jobs, or claim_expires_at for reclaims). Falls back to a 5 s paranoia poll only if the update watcher can't fire. For batched work, call claim_batch(worker_id, n) explicitly and ack with queue.ack_batch(ids, worker_id). Defaults: visibility 300 s.

Python: tasks (Huey-style decorators)
If you want a function call to turn into an enqueued job without wrapping queue.enqueue by hand:

@emails.task(retries=3, timeout_s=30)
def send_email(to: str, subject: str) -> dict:
    ...
    return {"sent_at": time.time()}

# Caller
r = send_email("alice@example.com", "Hi")   # enqueues, returns a TaskResult
print(r.get(timeout=10))                    # blocks until worker runs it
Worker side, either in-process or as its own process:

python -m honker worker myapp.tasks:db --queue=emails --concurrency=4
Auto-name is {module}.{qualname} (Huey/Celery convention). Explicit names with @emails.task(name="...") are recommended in prod so renames don't orphan pending jobs. Periodic tasks use @emails.periodic_task(crontab("0 3 * * *")). Full details in packages/honker/examples/tasks.py.

Python: stream (durable pub/sub)
stream = db.stream("user-events")

with db.transaction() as tx:
    tx.execute("UPDATE users SET name=? WHERE id=?", [name, uid])
    stream.publish({"user_id": uid, "change": "name"}, tx=tx)

async for event in stream.subscribe(consumer="dashboard"):
    await push_to_browser(event)
Each named consumer tracks its own offset in the _honker_stream_consumers table. subscribe replays rows past the saved offset, then transitions to live delivery on commit wake. The iterator auto-saves offset at most every 1000 events or every 1 second (whichever first) so a high-throughput stream doesn't hammer the single-writer slot. Override with save_every_n= / save_every_s=, or set both to 0 to disable auto-save and call stream.save_offset(consumer, offset, tx=tx) yourself (atomic with whatever you just did in that tx). At-least-once: a crash re-delivers in-flight events up to the last flushed offset.

Python: notify (ephemeral pub/sub)
async for n in db.listen("orders"):
    print(n.channel, n.payload)

with db.transaction() as tx:
    tx.execute("INSERT INTO orders (id, total) VALUES (?, ?)", [42, 99.99])
    tx.notify("orders", {"id": 42})
Listeners attach at current MAX(id); history is not replayed. Use db.stream() if you need durable replay. The notifications table is not auto-pruned. Call db.prune_notifications(older_than_s=…, max_keep=…) from a scheduled task. Task payloads have to be valid JSON so a Python writer and Node reader can share a channel.

Node.js
const { open } = require('@russellthehippo/honker-node');
const db = open('app.db');

// Atomic: business write + notify commit together
const tx = db.transaction();
tx.execute('INSERT INTO orders (id) VALUES (?)', [42]);
tx.notify('orders', { id: 42 });
tx.commit();

// updateEvents wakes on any commit to the db.
const ev = db.updateEvents();
let lastSeen = 0;
while (running) {
  await ev.next();
  const rows = db.query(
    'SELECT id, payload FROM _honker_notifications WHERE id > ? ORDER BY id',
    [lastSeen],
  );
  for (const row of rows) {
    handle(JSON.parse(row.payload));
    lastSeen = row.id;
  }
}
Current cross-language direct proof runs on every platform: Python -> Node wake through Node updateEvents(), and Node -> Python listener wake through Python listen().

Java / JVM
import dev.honker.*;

try (Database db = Honker.open("app.db")) {
    Queue emails = db.queue("emails");
    long id = emails.enqueue("{\"to\":\"alice@example.com\"}");

    Job job = emails.claimOne("worker-1").orElseThrow();
    sendEmail(job.payloadJson());
    job.ack();

    emails.saveResult(id, "{\"ok\":true}");
    emails.waitResultAsync(id, WaitOptions.timeout(Duration.ofSeconds(10)))
        .thenAccept(this::handleResult);
}
The JVM binding keeps JSON-library choice out of the core jar. Bring Jackson, Gson, Moshi, JSON-B, or a hand-written mapper by implementing JsonCodec<T>:

JsonCodec<Email> emailJson = new JsonCodec<>() {
    public String encode(Email value) {
        try {
            return mapper.writeValueAsString(value);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public Email decode(String json) {
        try {
            return mapper.readValue(json, Email.class);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
};

try (Database db = Honker.open("app.db")) {
    TypedQueue<Email> emails = db.queue("emails").typed(emailJson);
    emails.enqueue(new Email("alice@example.com"));

    TypedJob<Email> job = emails.claimOne("worker-1").orElseThrow();
    sendEmail(job.payload());
    job.ack();
}
Java handles are AutoCloseable, and worker/listener/subscriber options accept executors so application frameworks can own thread pools and shutdown.

Kotlin
honker("app.db").use { db ->
    val emails = db.queue("emails")
    emails.enqueueJson("""{"to":"alice@example.com"}""")

    emails.asFlow("worker-1").collect { job ->
        sendEmail(job.payloadJson())
        job.ack()
    }
}
Kotlin adds coroutine-friendly wrappers without duplicating the JVM runtime:

db.listen("orders")
    .asFlow()
    .collect { notification -> println(notification.payloadJson) }

db.stream("user-events")
    .asFlow()
    .collect { event -> push(event.payloadJson) }

val result = task.enqueueJson().await(Duration.ofSeconds(10))
Typed helpers use the same JsonCodec<T> seam:

val emailJson = object : JsonCodec<Email> {
    override fun encode(value: Email) = mapper.writeValueAsString(value)
    override fun decode(json: String) = mapper.readValue(json, Email::class.java)
}

db.queue("emails").enqueue(Email("alice@example.com"), emailJson)
val job = db.queue("emails").asFlow("worker-1").first()
sendEmail(job.decode(emailJson))
job.ack()
SQLite extension (any SQLite 3.9+ client)
.load ./libhonker_ext
SELECT honker_bootstrap();
INSERT INTO _honker_live (queue, payload) VALUES ('emails', '{"to":"alice"}');
SELECT honker_claim_batch('emails', 'worker-1', 32, 300);    -- JSON array
SELECT honker_ack_batch('[1,2,3]', 'worker-1');              -- DELETEs; returns count
SELECT honker_sweep_expired('emails');                       -- count moved to dead
SELECT honker_lock_acquire('backup', 'me', 60);              -- 1 = got it, 0 = held
SELECT honker_lock_release('backup', 'me');                  -- 1 = released
SELECT honker_rate_limit_try('api', 10, 60);                 -- 1 = under, 0 = at limit
SELECT honker_rate_limit_sweep(3600);                        -- drop windows >1h old
SELECT honker_cron_next_after('0 3 * * *', unixepoch());     -- 5-field cron
SELECT honker_cron_next_after('*/2 * * * * *', unixepoch()); -- 6-field cron
SELECT honker_cron_next_after('@every 5s', unixepoch());     -- interval schedule
SELECT honker_scheduler_register('nightly', 'backups',
  '0 3 * * *', '"go"', 0, NULL);                         -- register periodic task
SELECT honker_scheduler_register('fast', 'backups',
  '@every 5s', '"go"', 0, NULL);                         -- interval schedule
SELECT honker_scheduler_tick(unixepoch());                   -- JSON: fires due
SELECT honker_scheduler_soonest();                           -- min next_fire_at
SELECT honker_scheduler_unregister('nightly');               -- 1 = deleted
SELECT honker_queue_next_claim_at('emails');                 -- next run_at / reclaim deadline
SELECT honker_stream_publish('orders', 'k', '{"id":42}');    -- returns offset
SELECT honker_stream_read_since('orders', 0, 1000);          -- JSON array
SELECT honker_stream_save_offset('worker', 'orders', 42);    -- monotonic upsert
SELECT honker_stream_get_offset('worker', 'orders');         -- offset or 0
SELECT honker_result_save(42, '{"ok":true}', 3600);          -- save w/ 1h TTL
SELECT honker_result_get(42);                                -- value or NULL
SELECT honker_result_sweep();                                -- prune expired
SELECT notify('orders', '{"id":42}');
The extension shares _honker_live, _honker_dead, and _honker_notifications with the Python binding, so a Python worker can claim jobs any other language pushed via the extension. Schema compatibility is pinned by tests/test_extension_interop.py.

Design
This repo includes the honker SQLite loadable extension and bindings for Python, Node, Rust, Go, Ruby, Bun, Elixir, C++, .NET / C#, Java/JVM, and Kotlin.

For most applications, SQLite alone is sufficient. There are already great libraries that leverage SQLite for durable messaging. Huey is the one honker draws the most from. This project is inspired by it and seeks to do something similar across languages and frameworks by moving package logic into a SQLite extension.

For Postgres-backed apps, pg_notify + pg-boss or Oban is the equivalent. This library is for apps where SQLite is the primary datastore.

The extension has three primitives that tie it together: ephemeral pub/sub (notify()), durable pub/sub with per-consumer offsets (stream()), at-least-once work queue (queue()). All three are INSERTs inside your transaction, which lets a task "send" be atomic with your business write, and rollback drops everything.

The explicit goal is to do NOTIFY/LISTEN semantics without application-level polling, to achieve single-digit ms reaction time. If you use your app's existing SQLite file containing business logic, it will notify workers on every commit to the database. This means that most triggers will not result in anything happening: instead, workers just read the message/queue with no result. This "overtriggering" is on purpose and is the tradeoff for push-like semantics and fast reaction time.

WAL is the recommended default
The language bindings default to journal_mode = WAL because it gives concurrent readers with one writer and efficient fsync batching (wal_autocheckpoint = 10000). Other journal modes (DELETE, TRUNCATE, MEMORY) still work. The wake path is PRAGMA data_version, which increments on every commit in every journal mode and is visible across processes. What you lose in non-WAL modes is WAL's concurrent-read-while-writing property; correctness and cross-process wake do not depend on WAL.

One .db is the entire system (plus .db-wal / .db-shm sidecars if you've opted into WAL). You get every benefit of SQLite (embedded, local, durable, snapshot-able) that your app already uses.
Claim is one UPDATE … RETURNING via a partial index; ack is one DELETE. One writer at a time no matter the journal mode; concurrent readers come with WAL.
We poll PRAGMA data_version every 1 ms to detect commits from any connection in any journal mode. The counter increments on every commit and on checkpoint, so WAL truncation, journal-file comings-and-goings, and exact-size collisions are all handled correctly.
SQLite has no wire protocol. Consumers must initiate reads; server-push is impossible. Wake signal = counter increment → SELECT.
Transactions are cheap, so jobs, events, and notifications are rows in the caller's open with db.transaction() block in an "outbox"-type pattern.
We use PRAGMA data_version instead of stat(2) on the WAL file or kernel watchers (FSEvents/inotify/kqueue). data_version is a monotonic counter incremented by SQLite on every commit by any connection: it handles WAL truncation, clock skew, and rolled-back transactions correctly. Kernel watchers drop same-process writes on macOS, and stat(2) on (size, mtime) misses commits when the WAL is truncated then grows back to the same size. PRAGMA data_version works identically on Linux/macOS/Windows at ~1 ms granularity for negligible CPU. Cost: ~3.5 µs per query, ~3.5 ms/sec total at 1 kHz.
Single machine, single writer. SQLite's locking is designed for a single host. Two servers writing one .db over NFS will corrupt it. Shard by file, or switch to Postgres.
In-memory databases are not supported
Honker does not support SQLite in-memory database filenames such as :memory:, file::memory:?cache=shared, or file:<name>?mode=memory&cache=shared. Bare :memory: creates a separate database per connection, which would split Honker's writer, readers, and update watcher across different databases. SQLite's shared-memory URI forms can share state across multiple connections, but only inside one process, so they do not exercise Honker's cross-process worker/listener contract.

For tests and feature environments, use a temporary file-backed .db. It is still cheap and disposable, but it preserves the same SQLite locking, wake, crash/reopen, and multi-process semantics that Honker relies on in production.

Architecture
Wake path
One PRAGMA-poll thread per Database, queries data_version every 1 ms
Counter change → fan out a tick to each subscriber's bounded channel
Each subscriber runs SELECT … WHERE id > last_seen against a partial index, yields rows, returns to wait
100 subscribers = 1 poll thread
Idle listeners run zero SQL queries
Idle cost is a single PRAGMA data_version query per millisecond per database. Listener count scales for free because the wake signal is a SQLite counter read instead of a polling query.

SharedUpdateWatcher (in honker-core) owns the poll thread and fans out to N subscribers via bounded SyncSender<()> channels keyed by subscriber id. Each db.update_events() call registers a subscriber and returns a handle whose Drop auto-unsubscribes, so a dropped listener causes the bridge thread's rx.recv() -> Err and exits cleanly.

Wake backend (advanced)
Polling is the default. It's the only backend shipped in published wheels. Two opt-in alternatives exist behind Cargo features for source builds: kernel filesystem events, and an mmap read of SQLite's WAL index. Builds without the requested feature reject kernel / shm explicitly instead of silently substituting polling. Both experimental backends can give lower idle CPU or faster wakes, but they can also miss wakes or fire wakes you didn't ask for. All three watch for the database file being swapped under them; if that happens they shut down loudly — every subscriber sees an error from update_events() instead of hanging.

Binding support is tracked in BINDINGS.md. All maintained bindings route blocking wake waits through the same honker-core watcher, either in-process or through the shared extension ABI.

One thing changed for everyone, no opt-in needed: the polling backend now keeps its connection through transient SQLITE_BUSY / SQLITE_LOCKED errors during commits. Before, it would drop and reconnect, which could miss wakes on non-WAL journal modes (DELETE / TRUNCATE / PERSIST). Now it just retries the next tick.

Full reference — when to pick which, source-build flags, recovery patterns, what we haven't tested yet — at docs › Watcher backends.

Queue schema
_honker_live: pending + processing rows
Partial index: (queue, priority DESC, run_at, id) WHERE state IN ('pending','processing')
Claim = one UPDATE … RETURNING via that index
Ack = one DELETE
Retry-exhausted → _honker_dead (never scanned by claim path)
Partial-index on state means the claim hot path is bounded by the working-set size rather than the history size. A queue with 100k dead rows claims as fast as a queue with zero.

Claim iterator
async for job in q.claim(id) yields one job at a time via claim_batch(id, 1)
Job.ack() is one DELETE in its own transaction. Return is an honest bool: True iff the claim was still valid, False if the visibility window elapsed and another worker reclaimed.
Wakes on database update from any process, or when the next run_at / reclaim deadline arrives; a 5 s paranoia poll is the only fallback.
For batched work, call claim_batch(worker_id, n) directly and ack with queue.ack_batch(ids, worker_id). The library doesn't hide batching behind the iterator. The per-tx cost and the at-most-once visibility semantics are easier to reason about when the API doesn't try to be clever.

Transactional coupling
notify() is a SQL scalar function registered on the writer connection
INSERTs into _honker_notifications under the caller's open tx
queue.enqueue(…, tx=tx) and stream.publish(…, tx=tx) do the same
Rollback drops the job/event/notification with the rest of the tx
This is the transactional outbox pattern, by default, without a library to install. Business write and side-effect enqueue commit or roll back together. There is no separate dispatch table and no separate dispatcher process: the side-effect row is the committed row, and any process watching the db picks it up within ~1 ms.

Over-triggering quickly is better than over-triggering from polling
A data_version change wakes every subscriber on that Database, not just the ones whose channel committed
Each wasted wake = one indexed SELECT (microseconds)
A missed wake = a silent correctness bug
The library prefers waking ten listeners that don't care over missing one that does. Channel filtering happens in the SELECT path instead of the trigger notification. Many small queries are efficient in SQLite.

Retention
Queue jobs persist until ack; retry-exhausted rows move to _honker_dead
Stream events persist; each named consumer tracks its own offset
Notify is fire-and-forget and not auto-pruned
The caller chooses retention per primitive. db.prune_notifications(older_than_s=…, max_keep=…) is a tool you invoke. This keeps retention policy visible in the caller's code instead of inherited from a library default.

## Scheduler

Scheduler
The scheduler dispatches periodic jobs at schedule boundaries. It doesn’t run handlers itself. Instead, it enqueues into named queues that regular workers consume. This separation keeps scheduling lightweight and stops handler failures from affecting firing.

Registrations live in _honker_scheduler_tasks, which means every binding sees the same tasks. A Python process can register a schedule, and a Go worker can consume the enqueued jobs.
```python
import asyncio
from honker import Scheduler, crontab, every_s

scheduler = Scheduler(db)

scheduler.add(
    name="nightly-backup",
    queue="backups",
    schedule=crontab("0 3 * * *"),       # every day at 3am local time
    payload={"target": "s3"},
    expires=3600,                          # auto-drop if unclaimed after 1h
)

scheduler.add(
    name="heartbeat",
    queue="health",
    schedule=every_s(1),                   # every second
)

# Run forever. Multiple processes can call this — only one holds
# the leader lock and actually fires.
asyncio.run(scheduler.run())
```

Leader election
The scheduler acquires an advisory lock named honker-scheduler with a 60-second TTL. A periodic heartbeat extends the TTL during long idle waits. If the leader crashes, the TTL elapses and a standby takes over. Two schedulers running at the same time never double-fire because the lock is the sole gate, backed by BEGIN IMMEDIATE serialization.

This is binding-agnostic: a Python scheduler on one host and a Go scheduler on another host compete for the same lock through the database file. Whichever process holds the lock fires; the others stand by.

Missed-boundary catch-up
If the scheduler was down across multiple boundaries, the next tick walks forward and fires each missed boundary. Good for low-frequency schedules like “fire once per hour for the last 6 hours.” For high-frequency schedules where catch-up is unwanted, set expires_s= so stale jobs drop out of the claim window.

Schedule syntax
Honker accepts three schedule forms:

5-field cron: minute hour day-of-month month day-of-week
6-field cron: second minute hour day-of-month month day-of-week
@every <n><unit> such as @every 1s, @every 5m, @every 2h
Cron fields support:

* any value
N literal value
N-M inclusive range
*/K every K starting at the low end
N-M/K range with step
N,M,P list
All calendar arithmetic runs in the system local timezone. Set TZ=UTC if you want UTC boundaries.

DST is handled correctly. Spring-forward skips nonexistent local times; fall-back fires once at the earlier (EDT in US/Eastern) instance. Pinned by tests in the Rust cron module.

Where it lives
_honker_scheduler_tasks has one row per registered task: (name, queue, cron_expr, payload, priority, expires_s, next_fire_at).
cron_expr stores the canonical schedule expression, even for @every ....
Scheduler state is on disk, not in any process’s memory. Every binding sees the same registrations.

## QUEUES

A honker queue is a named row group in the _honker_live table. Jobs have a payload, a priority, a run_at time, an attempts counter, and (optionally) an expiration. A worker claims jobs atomically via an indexed UPDATE ... RETURNING, runs them, and acks (which DELETEs the row).

Every language binding shares the same on-disk format, so a Python enqueuer and a Go consumer can run against the same .db file.

Enqueue
Python
Node
Rust
Go
Ruby
Bun
Elixir
C++
SQL (extension)
import honker

db = honker.open("app.db")
q = db.queue("emails")

q.enqueue({"to": "alice@example.com"})
q.enqueue({"to": "bob@example.com"}, delay=60)       # claimable in 60s
q.enqueue({"to": "urgent@example.com"}, priority=10) # higher = picked first
q.enqueue({"to": "timely@example.com"}, expires=3600) # drops out after 1h

Claim and ack
Claiming moves a row to state='processing' and sets claim_expires_at = unixepoch() + visibility_timeout_s. If the worker doesn’t ack before that window elapses, another worker can reclaim.

Python
Node
Rust
Go
Ruby
Bun
Elixir
C++
SQL (extension)
### Async iterator — wakes on database updates or due deadlines.
async for job in q.claim("worker-1"):
    try:
        await send_email(job.payload)
        job.ack()
    except Exception as e:
        job.retry(delay_s=60, error=str(e))

Batch claim
For handlers that benefit from batching (DB writes, HTTP calls), claim N jobs in one transaction:

Python
Rust
Go
C++
SQL (extension)
jobs = q.claim_batch("worker-1", n=100)
for j in jobs:
    process(j.payload)
q.ack_batch([j.id for j in jobs], "worker-1")

Visibility timeout and heartbeat
Every claim has a claim_expires_at (default 300s). If the worker doesn’t ack or extend before that elapses, another worker can reclaim.

For long-running jobs, call heartbeat periodically to extend the window:

### Python
import asyncio

async def keepalive(job, stop):
    while not stop.is_set():
        await asyncio.sleep(60)
        job.heartbeat(extend_s=300)

async for job in q.claim("worker-1"):
    stop = asyncio.Event()
    hb = asyncio.create_task(keepalive(job, stop))
    try:
        await long_running(job.payload)
        job.ack()
    finally:
        stop.set()
        hb.cancel()
        try:
            await hb
        except asyncio.CancelledError:
            pass

Other bindings expose a plain job.heartbeat(extend_s) that you call on a timer.

Retry, fail, dead-letter
job.retry(delay_s, error) puts the row back in _honker_live with a new run_at. After max_attempts retries, it auto-moves to _honker_dead.
job.fail(error) moves it to _honker_dead unconditionally.
_honker_dead rows have last_error set; inspect with SELECT * FROM _honker_dead WHERE queue = 'emails'.
Where it lives
_honker_live: all currently-claimable or in-flight jobs. Partial index on (queue, priority DESC, run_at, id) WHERE state IN ('pending', 'processing') for O(log n) claims.
_honker_dead: exhausted or manually-failed jobs. Never auto-pruned; DELETE when you want.
A queue with 100k dead rows claims as fast as one with zero because the claim index excludes the dead state.

## Tasks

Decorators let you write queue code that looks synchronous:

import honker

db = honker.open("app.db")
q = db.queue("default")

@q.task(retries=3, timeout_s=30)
def send_email(to: str, subject: str) -> dict:
    ...
    return {"sent_at": time.time()}

# Caller side
r = send_email("alice@example.com", "Hi")   # enqueues, returns TaskResult
r.get(timeout=10)                            # blocks until worker finishes
# Or: await r.aget(timeout=10)

Calling send_email(...) does NOT run the function. It JSON-encodes the args into a job payload, enqueues on the default queue, and returns a TaskResult wrapping the job id.

A worker picks it up, runs the original function, stores the return value. The caller’s r.get() reads that stored value when the worker is done.

Auto-naming and the rename footgun
The default task name is f"{fn.__module__}.{fn.__qualname__}" — matches Huey/Celery.

If you rename the function, old jobs still reference the old name. They’ll dead-letter with unknown task: myapp.send_email. Two safe-rename patterns:

Explicit name from day one: @q.task(name="send-email"). Rename the Python function freely; the task name is stable.
Stub the old name: keep a wrapper under the old @q.task(name="myapp.old_name") that calls the new function.
Docs recommend pattern 1.

Worker
The worker loop dispatches by name via a process-global registry. Two ways to run it:

CLI
Terminal window
python -m honker worker myapp.tasks:db --queue=default --concurrency=4

The positional argument is an import path (myapp.tasks) followed by :variable_name — db is the honker.Database instance. Importing that module fires the @q.task() decorators as a side effect, populating the registry.

Flags:

--queue NAME — repeat to drain multiple queues. Default: every queue with registered tasks.
--concurrency N — workers per queue. Default: os.cpu_count().
--list — print registered tasks and exit.
In-process
For embedding a worker inside an existing async process (FastAPI lifespan, a long-running script):

import asyncio
import honker

db = honker.open("app.db")

# ... @q.task-decorated functions imported and registered here ...

asyncio.run(db.run_workers(concurrency=4))

db.run_workers blocks until the passed stop_event is set or the task is cancelled.

Defaults
Result storage: on, 1h TTL. r.get() works out of the box. Pass store_result=False on a decorator for fire-and-forget tasks (logs, webhook posts, cleanup) to skip the extra INSERT.
Retries: inherited from the queue’s max_attempts. Override per-task with @q.task(retries=N).
Retry delay: 60s. Override with retry_delay_s=.
Timeout: none. @q.task(timeout_s=30) wraps the call in asyncio.wait_for. On timeout, the job retries with timeout after 30s as the error. For sync functions, the task dispatches onto a background thread so a blocking task doesn’t freeze peer workers.
Periodic tasks
from honker import crontab, every_s

@q.periodic_task(crontab("0 3 * * *"))
def nightly_backup():
    ...

@q.periodic_task(every_s(1))
def heartbeat():
    ...

Registers the function in the task registry AND in the scheduler. The scheduler enqueues a fixed payload (no args) on each schedule boundary; the worker picks it up and dispatches through the same decorator-task path.

Same default-on-none / explicit-name pattern: @q.periodic_task(crontab, name="nightly") to stabilize the name.

Edge cases
Arguments must be JSON-serializable. Raw ints, strs, floats, bools, None, lists, and dicts. Passing a datetime raises TypeError at enqueue time — honest, not silent garbage in the payload.

Unknown task names go to dead-letter with unknown task: foo.bar. Registered tasks: [...] so the operator can see what the worker has vs. what was queued.

Sync task blocking the event loop. A sync def is dispatched onto asyncio.to_thread — multiple sync tasks run in parallel threads, the event loop stays responsive.

Hot reload / same-function re-register. Calling the decorator twice on the same function is idempotent. Registering two different functions under the same explicit name= raises at import time.

What’s stored where
_honker_live — pending + in-flight job rows. Payload is a JSON envelope: {"__honker_task__": {"task": "...", "args": [...], "kwargs": {...}}}.
_honker_dead — exhausted retries + unknown tasks + explicit .fail(...) calls.
_honker_results — return values keyed by job id. Expires at unixepoch() + result_ttl_s.
_honker_scheduler_tasks — periodic task registrations (one row per decorated @periodic_task).
All tables share the same .db file as your business data.

## Example

File: examples/demo.py
  Size: 972 B
  """Minimal honker demo: enqueue a job, claim it, ack it."""
  import asyncio
  import os

  import honker


  async def main():
      if os.path.exists("app.db"):
          os.remove("app.db")

      db = honker.open("app.db")
      emails = db.queue("emails")

      with db.transaction() as tx:
          tx.execute(
              "CREATE TABLE IF NOT EXISTS orders "
              "(id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)"
          )

      with db.transaction() as tx:
          tx.execute("INSERT INTO orders (user_id, amount) VALUES (?, ?)", [42, 19.99])
          emails.enqueue(
              {"to": "alice@example.com", "body": "Receipt for 19.99"}, tx=tx
          )

      async def worker():
          async for job in emails.claim("w1"):
              print(f"sending email to {job.payload['to']}: {job.payload['body']}")
              job.ack()
              return

      await asyncio.wait_for(worker(), timeout=2.0)
      print("done")


  if __name__ == "__main__":
      asyncio.run(main())
