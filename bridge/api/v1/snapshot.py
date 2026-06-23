import json
from fastapi import APIRouter, HTTPException
from bridge.services.redis_client import redis_pool
from bridge.models.schemas import NormalizedSnapshot

router = APIRouter()

@router.get("/", response_model=NormalizedSnapshot)
async def get_snapshot():
    """
    Returns the latest validated snapshot from the memory pool.
    This is the primary context endpoint for your AI agent.
    """
    if not redis_pool.client:
        raise HTTPException(status_code=500, detail="Database client connection uninitialized.")
        
    # Read straight from Redis - O(1) performance
    raw_data = await redis_pool.client.get("snapshot:latest")
    
    if raw_data is None:
        raise HTTPException(
            status_code=503,
            detail="Snapshot not yet available. The background worker may still be initializing."
        )
        
    # Unpack the JSON string back into your Pydantic schema validation pipeline
    return NormalizedSnapshot(**json.loads(raw_data))

@router.get("/summary")
async def get_summary():
    """
    Lightweight overview endpoint bypassing detailed host/service payload lists.
    """
    if not redis_pool.client:
        raise HTTPException(status_code=500, detail="Database client connection uninitialized.")
        
    raw_data = await redis_pool.client.get("snapshot:latest")
    if raw_data is None:
        raise HTTPException(status_code=503, detail="Snapshot data temporarily unavailable.")
        
    snap = NormalizedSnapshot(**json.loads(raw_data))
    return {
        "collected_at": snap.collected_at,
        "summary": snap.summary,
        "health_score": snap.summary.health_score  # Evaluates dynamic property
    }