import asyncio
import json
from datetime import datetime, timezone
import os
from bridge.services.redis_client import redis_pool
from bridge.services.centreon_api import centreon_api_client
from bridge.config import POLLING_INTERVAL
from bridge.models.schemas import NormalizedSnapshot, StatusSummary, NormalizedHost, NormalizedService
from bridge.services.metrics_saver import save_snapshot_to_timescale

class LiveMetricPipelineWorker:
    def __init__(self, interval_seconds: int = 10):
        self.interval = interval_seconds
        self.is_running = False

    async def run_loop(self):
        self.is_running = True
        print(f" Live Centreon API polling sequence initialized. Interval: {self.interval}s")
        
        while self.is_running:
            try:
                now = datetime.now(timezone.utc)
                
                # Request live array block straight from Centreon
                raw_resources = await centreon_api_client.fetch_resource_statuses()
                
                if not raw_resources:
                    print("[Pipeline Worker]: Empty telemetry payload received. Retrying in next loop...")
                    await asyncio.sleep(self.interval)
                    continue

                parsed_hosts = {}
                parsed_services = []
                
                ok_count, warn_count, crit_count, unk_count = 0, 0, 0, 0
                hosts_up, hosts_down = 0, 0

                for idx, item in enumerate(raw_resources):
                    if not isinstance(item, dict):
                        continue

                    if idx % 10 == 0 and idx > 0:
                        await asyncio.sleep(0)

                    status_block = item.get("status") or {}
                    status_name = status_block.get("name", "UNKNOWN").upper()
                    status_code = status_block.get("code", 3)
                    info_text = item.get("information", "") or ""

                    parent_block = item.get("parent") or {}
                    parent_host_name = parent_block.get("name", "Unknown-Host")
                    item_type = str(item.get("type", "")).lower()

                    # 1. Process Host Identity Elements
                    if item_type == "host":
                        host_name = item.get("name", "Unknown-Host")
                        if host_name not in parsed_hosts:
                            parsed_hosts[host_name] = NormalizedHost(
                                name=host_name,
                                status=status_name,
                                status_code=int(status_code),
                                last_check=now,
                                output=info_text
                            )
                            if status_name == "UP":
                                hosts_up += 1
                            else:
                                hosts_down += 1
                    
                    # 2. Process Service Telemetry Metrics Row
                    elif item_type == "service":
                        service_model = NormalizedService(
                            host_name=parent_host_name,
                            name=item.get("name", "Service Component"),
                            status=status_name,
                            status_code=int(status_code),
                            last_check=now,
                            output=info_text,
                            performance_data=str(item.get("performance_data") or "")
                        )
                        parsed_services.append(service_model)

                        try:
                            code_int = int(status_code)
                        except (ValueError, TypeError):
                            code_int = 3

                        if code_int == 0:
                            ok_count += 1
                        elif code_int == 1:
                            warn_count += 1
                        elif code_int == 2:
                            crit_count += 1
                        else:
                            unk_count += 1

                        if parent_host_name not in parsed_hosts:
                            parent_status_block = parent_block.get("status") or {}
                            parent_status = parent_status_block.get("name", "UP").upper()
                            parent_code = parent_status_block.get("code", 0)
                            
                            parsed_hosts[parent_host_name] = NormalizedHost(
                                name=parent_host_name,
                                status=parent_status,
                                status_code=int(parent_code),
                                last_check=now,
                                output="Resolved dynamically via service relationship topology."
                            )
                            if parent_status == "UP":
                                hosts_up += 1
                            else:
                                hosts_down += 1

                if not parsed_hosts:
                    parsed_hosts["Centreon-central"] = NormalizedHost(
                        name="Centreon-central", status="UP", status_code=0, last_check=now, output="Fallback asset."
                    )
                    hosts_up = 1

                summary = StatusSummary(
                    hosts_up=hosts_up,
                    hosts_down=hosts_down,
                    services_ok=ok_count,
                    services_warning=warn_count,
                    services_critical=crit_count,
                    services_unknown=unk_count
                )

                snapshot = NormalizedSnapshot(
                    collected_at=now,
                    summary=summary,
                    hosts=list(parsed_hosts.values()),
                    services=parsed_services,
                    recent_events=[]
                )

                # Write cleanly formatted state snapshots down to Redis memory block
                if redis_pool.client:
                    snapshot_json = snapshot.model_dump(mode="json")
                    await redis_pool.client.set("snapshot:latest", json.dumps(snapshot_json), ex=300)
                    print(f"[Pipeline Worker]: Live data snapshot processed ({len(parsed_services)} services mapped) at {now.strftime('%H:%M:%S')}")
                    
                    # Stream the new serialized operational JSON payload straight to the TimescaleDB Hypertable
                    await save_snapshot_to_timescale(snapshot_json)

            except Exception as e:
                print(f"Unexpected execution error in ingestion routine: {str(e)}")
            
            await asyncio.sleep(self.interval)

    def stop(self):
        self.is_running = False

polling_pipeline_worker = LiveMetricPipelineWorker(interval_seconds=POLLING_INTERVAL)