import re
from datetime import datetime, timezone
from bridge.models.schemas import NormalizedService

def parse_raw_metric(host_name: str, service_name: str, raw_info: str) -> NormalizedService:
    """
    Parses unstructured infrastructure strings into validated Pydantic instances.
    """
    status_str = "OK"
    status_code = 0
    
    # Check for monitoring status string flags
    if "CRITICAL:" in raw_info or "CRITICAL -" in raw_info:
        status_str = "CRITICAL"
        status_code = 2
    elif "WARNING:" in raw_info or "WARNING -" in raw_info:
        status_str = "WARNING"
        status_code = 1
    elif "UNKNOWN:" in raw_info or "UNKNOWN -" in raw_info:
        status_str = "UNKNOWN"
        status_code = 3
        
    # Strip status prefixes to keep metric text clean
    clean_output = re.sub(r'^(OK|CRITICAL|WARNING|UNKNOWN)[:\s-]*', '', raw_info).strip()
    
    # Separate metrics data from performance data if a pipe '|' character exists
    perf_data = ""
    if "|" in raw_info:
        parts = raw_info.split("|", 1)
        clean_output = re.sub(r'^(OK|CRITICAL|WARNING|UNKNOWN)[:\s-]*', '', parts[0]).strip()
        perf_data = parts[1].strip()

    return NormalizedService(
        host_name=host_name,
        name=service_name,
        status=status_str,
        status_code=status_code,
        acknowledged=False,
        in_downtime=False,
        last_check=datetime.now(timezone.utc),
        last_state_change=datetime.now(timezone.utc),
        output=clean_output,
        performance_data=perf_data,
        groups=["production-central"]
    )