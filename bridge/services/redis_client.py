import redis.asyncio as aioredis
from typing import Optional

class RedisPipelinePool:
    def __init__(self, redis_url: str = "redis://127.0.0.1:6379/0"):
        self.redis_url = redis_url
        self.client: Optional[aioredis.Redis] = None

    def connect(self):
        """Initializes a non-blocking asynchronous Redis connection pool."""
        self.client = aioredis.from_url(
            self.redis_url, 
            encoding="utf-8", 
            decode_responses=True,
            max_connections=20
        )
        print(" [Redis Client]: Connection pool mapped successfully.")

    async def disconnect(self):
        if self.client:
            await self.client.close()
            print(" [Redis Client]: Connection pool flushed.")

redis_pool = RedisPipelinePool()