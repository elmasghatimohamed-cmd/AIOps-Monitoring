# bridge/api/v1/router.py
from fastapi import APIRouter
from bridge.api.v1.snapshot import router as snapshot_router

router = APIRouter()

router.include_router(snapshot_router, prefix="/snapshot", tags=["Snapshot Engine"])