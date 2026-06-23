import json
from bridge.services.redis_client import redis_pool

class AgentContextBuilder:
    def __init__(self):
        # Target the running Redis cache instance directly across folder horizons
        self.redis = redis_pool.client

    async def get_live_markdown_context(self) -> str:
        """
        Pull metrics out of Redis memory blocks and outputs data into clean Markdown format.
        """
        if not self.redis:
            return "Redis data caching layer is currently unreachable."

        raw_snapshot = await self.redis.get("snapshot:latest")
        if not raw_snapshot:
            return " Waiting for the next inbound polling metrics pipeline loop execution..."

        try:
            snapshot_data = json.loads(raw_snapshot)
            summary = snapshot_data.get("summary", {})
            hosts = snapshot_data.get("hosts", [])
            services = snapshot_data.get("services", [])
            collected_at = snapshot_data.get("collected_at", "Unknown")

            # 1. Pipeline Summary Header
            markdown = f"Data Collected At: {collected_at}\n"
            markdown += (
                f"Infrastructure Overview Summary -> Hosts UP: {summary.get('hosts_up', 0)} | "
                f"Services OK: {summary.get('services_ok', 0)} | "
                f"Warnings: {summary.get('services_warning', 0)} | "
                f"Criticals: {summary.get('services_critical', 0)}\n\n"
            )

            # 2. Hosts Inventory Layer
            markdown += "#### Supervised Infrastructure Topology Assets:\n"
            markdown += "| Monitored Host Asset | Status | State Output Text Line |\n| :--- | :--- | :--- |\n"
            for host in hosts:
                markdown += f"| {host.get('name')} | **{host.get('status')}** | {host.get('output')} |\n"
            markdown += "\n"

            # 3. Core Metric Matrix
            markdown += "#### Monitored Active Service Components:\n"
            markdown += "| Service Check Target | Status State | Diagnostic Metric Logs Information |\n| :--- | :--- | :--- |\n"
            for service in services:
                status = service.get("status", "UNKNOWN").upper()
                clean_output = service.get("output", "").replace("\n", " ").strip()
                markdown += f"| {service.get('name')} | {status} | {clean_output} |\n"

            return markdown

        except Exception as e:
            return f"Context Generation Parsing Exception: {str(e)}"

agent_context_builder = AgentContextBuilder()