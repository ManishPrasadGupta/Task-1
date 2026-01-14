import asyncio
import httpx
import time
import random

URL = "http://127.0.0.1:8000/event"
CONCURRENCY = 1000  # Number of concurrent requests

EVENT = {
    "user_id": 123,
    "timestamp": "2026-01-12T13:01:00Z",
    "metadata": {"page": "/home", "click": True}
}

async def send_event(client, event):
    # Send one POST event
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