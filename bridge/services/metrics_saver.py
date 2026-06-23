# bridge/services/metrics_saver.py
import json
from datetime import datetime, timezone
from bridge.database import tsdb

async def save_snapshot_to_timescale(snapshot_data: dict):
    """
    Parsing live Centreon snapshot payload and batching individual service 
    metrics into TimescaleDB hypertable.
    """
    if not tsdb.pool:
        print("[TimescaleDB Warning]: Database pool not available for ingestion.")
        return

    # Extract services list from the payload structure
    services = snapshot_data.get("services", [])
    if not services:
        return

    timestamp = datetime.now(timezone.utc)
    host_name = snapshot_data.get("host_name", "centreon-server")

    # Prepare batch records for high-speed insertion
    records = []
    
    for service in services:
        service_name = service.get("name", "Unknown")
        status = service.get("status", "UNKNOWN")
        output_text = service.get("output", "")
        
        # Parse common metric signatures from output text
        metric_value = None
        metric_name = "raw_output"
        
        try:
            if "Load average:" in output_text:
                parts = output_text.split("Load average:")[1].split(",")
                metric_value = float(parts[0].strip())
                metric_name = "load_1min"
            elif "usage is" in output_text:
                metric_value = float(output_text.split("usage is")[1].split("%")[0].strip())
                metric_name = "percentage_utilization"
            elif "used out of" in output_text:
                metric_value = float(output_text.split("used out of")[0].replace("used", "").strip().split(" ")[0].replace("MB", ""))
                metric_name = "mb_used"
        except Exception:
            metric_value = 0.0

        # Construct database record matching hypertable indices
        records.append((
            timestamp,
            host_name,
            service_name,
            metric_name,
            metric_value,
            status,
            json.dumps({"raw_output": output_text})  # Keep raw data inside JSONB tags
        ))

    # Bulk execute inside an async transaction block
    if records:
        try:
            async with tsdb.pool.acquire() as connection:
                async with connection.transaction():
                    await connection.executemany("""
                        INSERT INTO metrics (timestamp, host, service, metric_name, metric_value, status, tags)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """, records)
            print(f"[TimescaleDB Ingestion]: Batched and saved {len(records)} metric rows.")
        except Exception as e:
            print(f"[TimescaleDB Ingestion Error]: Bulk insert operation failed: {e}")