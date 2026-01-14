from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import aiosqlite
from datetime import datetime
import asyncio

DB_PATH = "inventory.db"
ITEM_NAME = "A"
INITIAL_STOCK = 100


# Create tables if needed
async def create_tables():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item TEXT PRIMARY KEY,
            stock INTEGER NOT NULL
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            timestamp TEXT
        )
        """)
        await db.execute("""
        INSERT OR IGNORE INTO inventory (item, stock) VALUES (?, ?)
        """, (ITEM_NAME, INITIAL_STOCK))
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/buy_ticket")
async def buy_ticket(retries: int = 3):  # Add some retries for busy DB
    for attempt in range(retries):
        async with aiosqlite.connect(DB_PATH, timeout=1.0) as db:
            try:
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    "SELECT stock FROM inventory WHERE item = ?", (ITEM_NAME,))
                row = await cursor.fetchone()
                stock = row[0] if row else 0
                if stock > 0:
                    await db.execute(
                        "UPDATE inventory SET stock = stock - 1 WHERE item = ?",
                        (ITEM_NAME,))
                    await db.execute(
                        "INSERT INTO purchases (item, timestamp) VALUES (?, ?)",
                        (ITEM_NAME, datetime.utcnow().isoformat()))
                    await db.commit()
                    return JSONResponse({"message": "Purchase successful"}, status_code=status.HTTP_200_OK)
                else:
                    await db.commit()
                    return JSONResponse({"message": "Sold out"}, status_code=status.HTTP_410_GONE)
            except Exception as e:
                await db.rollback()
                if "database is locked" in str(e).lower() and attempt < retries - 1:
                    await asyncio.sleep(0.1)
                    continue
                return JSONResponse({"message": "Error, please retry"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)