from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

# ── Status Summary Model ──────────────────────────────────────────────────────
class StatusSummary(BaseModel):
    hosts_up: int = 0
    hosts_down: int = 0
    hosts_unreachable: int = 0
    hosts_pending: int = 0
    services_ok: int = 0
    services_warning: int = 0
    services_critical: int = 0
    services_unknown: int = 0

    @property
    def total_hosts(self) -> int:
        return self.hosts_up + self.hosts_down + self.hosts_unreachable + self.hosts_pending

    @property
    def total_services(self) -> int:
        return self.services_ok + self.services_warning + self.services_critical + self.services_unknown

    @property
    def health_score(self) -> float:
        """Composite index rating: 0.0 (all down) → 1.0 (all nominal)"""
        h_total = self.total_hosts or 1
        s_total = self.total_services or 1
        h_score = self.hosts_up / h_total
        s_score = self.services_ok / s_total
        return round((h_score + s_score) / 2, 4)

# ── Host Model ────────────────────────────────────────────────────────────────
class NormalizedHost(BaseModel):
    id: Optional[int] = None
    name: str
    alias: str = ""
    address: str = ""
    status: str                         # UP | DOWN | UNREACHABLE | PENDING
    status_code: int
    acknowledged: bool = False
    in_downtime: bool = False
    last_check: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    output: str = ""
    groups: list[str] = Field(default_factory=list)

# ── Service Model ─────────────────────────────────────────────────────────────
class NormalizedService(BaseModel):
    id: Optional[int] = None
    host_id: Optional[int] = None
    host_name: str
    name: str
    status: str                         # OK | WARNING | CRITICAL | UNKNOWN | PENDING
    status_code: int
    acknowledged: bool = False
    in_downtime: bool = False
    last_check: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    output: str = ""
    performance_data: str = ""
    check_interval: int = 0
    groups: list[str] = Field(default_factory=list)

# ── Event Model ───────────────────────────────────────────────────────────────
class NormalizedEvent(BaseModel):
    id: Optional[int] = None
    host_id: Optional[int] = None
    host_name: str
    service_id: Optional[int] = None
    service_name: str = ""
    status: str
    event_type: str = "SOFT"            # SOFT | HARD
    output: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    acknowledged: bool = False

# ── Full Canonical Snapshot Model (AI Context Payload) ────────────────────────
class NormalizedSnapshot(BaseModel):
    collected_at: datetime
    summary: StatusSummary
    hosts: list[NormalizedHost]
    services: list[NormalizedService]
    recent_events: list[NormalizedEvent]