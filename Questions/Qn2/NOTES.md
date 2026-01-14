### Core Requirements

- **Single POST endpoint** (`/event`)
- **Immediate HTTP 202 response** (non-blocking)
- **Buffering:** No per-request DB writes, group by batch
- **Persistence:** Data to SQL DB, JSON safety
- **Resilience:** Handles DB slowdowns/outages; server keeps accepting events

## 1. **Imports and Globals**

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from collections import deque
import threading
import time
import json
import aiosqlite
import asyncio
from contextlib import asynccontextmanager

event_buffer = deque()
buffer_lock = threading.Lock()
DB_PATH = "firehose.db"
simulate_db_outage = False
```

**What’s here:**

- **event_buffer:** an in-memory, thread-safe queue to batch incoming events.
- **buffer_lock:** ensures event buffer isn’t corrupted by simultaneous access.
- **simulate_db_outage:** simulates DB unavailability by sleeping for 5s during batch flush.

## 2. **Database Table Creation**

```python
async def create_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            timestamp TEXT,
            metadata TEXT
        )
        """)
        await db.commit()
```

**Why:** Ensures the SQLite table exists before ingestion starts. All event fields, including arbitrary JSON metadata, are stored safely as a string using `json.dumps`.

## 3. **Application Startup/Lifespan Hook**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_table()
    task = asyncio.create_task(batch_db_flusher())
    yield
    task.cancel()
app = FastAPI(lifespan=lifespan)
```

- On startup: create events table, start batch DB flush task
- On shutdown: cancel batch flush task

## 4. **Batching & Buffer Flushing Task**

```python
async def batch_db_flusher(batch_size=100, flush_interval=2):
    while True:
        await asyncio.sleep(flush_interval)
        batch = []
        with buffer_lock:
            while event_buffer and len(batch) < batch_size:
                batch.append(event_buffer.popleft())
        if batch:
            if simulate_db_outage:
                print("Simulated DB outage: sleeping 5 seconds")
                await asyncio.sleep(5)
            try:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.executemany(
                        "INSERT INTO events (user_id, timestamp, metadata) VALUES (?, ?, ?)",
                        [
                            (e["user_id"], e["timestamp"], json.dumps(e["metadata"])) for e in batch
                        ]
                    )
                    await db.commit()
                    print(f"{len(batch)} events flushed to DB.")
            except Exception as e:
                print("Error flushing batch:", e)
                with buffer_lock:
                    for evt in reversed(batch):
                        event_buffer.appendleft(evt)
                await asyncio.sleep(1)
```

### **How It Works:**

- **Wakes every `flush_interval` seconds**
- **Pulls up to `batch_size` events from buffer** (using the lock)
- **Tries to flush to DB:** If a simulated outage is set, it sleeps 5 seconds before proceeding.
- **Error on DB write:** Returns batch to buffer (so events aren’t lost!) Sleeps a little, retries.

**Why is metadata handled safely?**

- Always stored using `json.dumps`, so arbitrary/nested data placed into the TEXT field as serialized JSON (no SQL injection risk; not interpolated into SQL strings).

## 5. **Event Ingestion Endpoint**

```python
@app.post("/event")
async def handle_event(request: Request):
    data = await request.json()
    with buffer_lock:
        event_buffer.append(data)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"message": "Event accepted"})
```

- Accepts POST JSON payload
- It’s **non-blocking:** immediately adds event to `deque` and returns 202.
- Does **not** wait for DB write!

## 6. **Load Test Script**

```python
# ... imports ...
URL = "http://127.0.0.1:8000/event"
CONCURRENCY = 1000

EVENT = {
    "user_id": 123,
    "timestamp": "2026-01-12T13:01:00Z",
    "metadata": {"page": "/home", "click": True}
}

async def send_event(client, event):
    r = await client.post(URL, json=event)
    return r.status_code

async def main():
    async with httpx.AsyncClient() as client:
        tasks = [
            send_event(client, {
                "user_id": i,
                "timestamp": f"2026-01-12T13:{i//60:02}:{i%60:02}Z",
                "metadata": {"page": f"/page{i%10}", "click": bool(random.getrandbits(1))}
            }) for i in range(CONCURRENCY)
        ]
        start = time.perf_counter()
        res = await asyncio.gather(*tasks)
        end = time.perf_counter()
        print(f"Sent {len(res)} requests in {end - start:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())
```

### **How It Works:**

- **CONCURRENCY = 1000**: Sends 1,000 POSTs concurrently to `/event`
- Each request simulates valid event data, randomizing some metadata.
- Measures how long for all requests to complete.

---

## **How the System Handles Outages**

- If DB is locked (`simulate_db_outage = True`), batch flush blocks—but incoming requests keep getting buffered!
- Once the DB is available again, accumulated buffer is flushed — **no events lost**.

## **Architecture Summary**

- **API Layer:** FastAPI, exposes `/event`, non-blocking.
- **Buffering/Batching:** In-memory `deque` with thread lock.
- **Flushing:** Background async task drains & inserts batches.
- **Resilience:** If DB write fails, batch goes back to buffer for retry.
- **Security:** `metadata` always safely encoded as JSON string before DB write, protects against injection.
- **Testing:** Async script firehoses events to endpoint for throughput demo.

### **How to Run**

- Start FastAPI server (`uvicorn firehose_collector:app`)
- Send load test events using the provided script.
- Optionally, toggle `simulate_db_outage = True` to see server resilience under DB outages.
