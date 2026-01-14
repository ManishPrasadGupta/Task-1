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
simulate_db_outage = True


# Table creation
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


# This ensures the DB table is created when the app starts.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup events
    await create_table()
    task = asyncio.create_task(batch_db_flusher())
    yield
    task.cancel()  
app = FastAPI(lifespan=lifespan)


# It's an async task that runs forever, flushing events every N seconds or if buffer reaches threshold.
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

                 # re-buffer failed batch so no data loss
                with buffer_lock:
                    for evt in reversed(batch):
                        event_buffer.appendleft(evt)
                await asyncio.sleep(1)


@app.post("/event")
async def handle_event(request: Request):
    data = await request.json()
    # the event is buffered in memory for batch insertion
    with buffer_lock:
        event_buffer.append(data)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"message": "Event accepted"})