# bridge/database.py
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DB_DSN = os.getenv("TIMESCALE_DSN")

class TimescaleDatabase:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Initializes the asyncpg connection pool."""
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=DB_DSN,
                    min_size=2,
                    max_size=10
                )
                print("[TimescaleDB]: Connection pool initialized successfully.")
            except Exception as e:
                print(f"[TimescaleDB Error]: Failed to create connection pool: {e}")
                raise e

    async def disconnect(self):
        """Close the connection pool on application shutdown."""
        if self.pool:
            await self.pool.close()
            print("[TimescaleDB]: Connection pool closed.")

tsdb = TimescaleDatabase()