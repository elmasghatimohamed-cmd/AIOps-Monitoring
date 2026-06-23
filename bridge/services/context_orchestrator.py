import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from bridge.services.redis_client import redis_pool
from bridge.database import tsdb
from bridge.services.vector_store import vector_memory

class ContextOrchestrator:
    def __init__(self):
        self.default_lookahead = 15

    def classify_intent(self, user_query: str) -> str:
        """
        Lightweight classification engine to determine memory routing depth.
        """
        query_lower = user_query.lower()
        
        if any(w in query_lower for w in ["why", "root cause", "incident", "crash", "fail", "broken", "remediate", "wrong", "anomaly", "anomalies", "slow", "critical"]):
            return "ROOT_CAUSE"
        # Trend Analysis triggers wider window metric evaluation
        elif any(w in query_lower for w in ["history", "trend", "average", "past", "baseline", "chart", "last", "minutes", "hours", "numbers", "today", "records", "predict", "forecast", "future"]):
            return "TREND_ANALYSIS"
        
        return "CURRENT_STATUS"

    async def gather_context(self, user_query: str, host_filter: str = "srv-prod-app-01") -> dict:
        """
        Collects cross-referenced data vectors optimized for 10-second polling frequencies.
        Combines Real-time caching, Dual-window historical time-series, Semantic knowledge, 
        and local ML predictive matrix lookaheads into a unified context packet.
        """
        intent = self.classify_intent(user_query)
        context = {
            "intent_classification": intent,
            "redis": {},
            "timescaledb": {},
            "chromadb": {},
            "machine_learning_forecast": {}
        }

        print(f"[Context Orchestrator]: Classified query intent as '{intent}'")

        # Pull real-time snapshot state from Redis cache
        if redis_pool.client:
            raw_snapshot = await redis_pool.client.get("snapshot:latest")
            if raw_snapshot:
                data_str = raw_snapshot.decode('utf-8') if isinstance(raw_snapshot, bytes) else raw_snapshot
                full_snap = json.loads(data_str)
                context["redis"] = {
                    "collected_at": full_snap.get("collected_at"),
                    "summary": full_snap.get("summary"),
                    # Isolate any actively warning/critical metrics right now
                    "active_alerts": [
                        {"service": s.get("name"), "status": s.get("status"), "output": s.get("output")}
                        for s in full_snap.get("services", []) if s.get("status") != "OK"
                    ]
                }

        # If there is a live active infrastructure issue in Redis automatically pull all telemetry data
        has_active_alerts = len(context["redis"].get("active_alerts", [])) > 0
        if has_active_alerts:
            print("[Context Orchestrator Override]: Live anomalies detected. Elevating contextual scope to all layers.")

        # Dual-Window High-Density Time-Series Forensics
        if (intent in ["TREND_ANALYSIS", "ROOT_CAUSE"] or has_active_alerts) and tsdb.pool:
            try:
                async with tsdb.pool.acquire() as connection:
                    # Immediate Micro-Forensics Window (Last 3 minutes)
                    micro_rows = await connection.fetch("""
                        SELECT service, metric_name, 
                               AVG(metric_value) as avg_value, 
                               MAX(metric_value) as max_value,
                               COUNT(*) as data_points
                        FROM metrics
                        WHERE timestamp >= NOW() - INTERVAL '3 minutes'
                        GROUP BY service, metric_name;
                    """)
                    
                    # Macro Historical Baseline Window (Last 3 days)
                    macro_rows = await connection.fetch("""
                        SELECT service, metric_name, 
                               MAX(metric_value) as historical_max,
                               AVG(metric_value) as historical_avg,
                               COUNT(*) as total_samples
                        FROM metrics
                        WHERE timestamp >= NOW() - INTERVAL '3 days'
                        GROUP BY service, metric_name;
                    """)

                    context["timescaledb"] = {
                        "immediate_3min_window": [
                            {
                                "service": r["service"],
                                "metric_name": r["metric_name"],
                                "peak_max": round(r["max_value"], 2) if r["max_value"] is not None else 0.0,
                                "average": round(r["avg_value"], 2) if r["avg_value"] is not None else 0.0,
                                "samples_captured": r["data_points"]
                            } for r in micro_rows
                        ],
                        "historical_3day_baseline": [
                            {
                                "service": r["service"],
                                "metric_name": r["metric_name"],
                                "all_time_peak_max": round(r["historical_max"], 2) if r["historical_max"] is not None else 0.0,
                                "historical_average": round(r["historical_avg"], 2) if r["historical_avg"] is not None else 0.0,
                                "total_data_points_analyzed": r["total_samples"]
                            } for r in macro_rows
                        ]
                    }
            except Exception as e:
                print(f"[Context Orchestrator Error]: Failed to fetch TimescaleDB dual-window aggregates: {e}")

        # Semantic Space Cross-Referencing
        if (intent == "ROOT_CAUSE" or has_active_alerts):
            active_alerts = context["redis"].get("active_alerts", [])
            
            if active_alerts:
                failing_service = active_alerts[0]["service"]
                alert_status = active_alerts[0]["status"]
                alert_output = active_alerts[0]["output"].lower()
                
                symptom_registry = {
                    "partitioning": ["partition", "retention", "storage", "maintenance", "tables", "data_bin", "logs"],
                    "cpu": ["utilization", "stress", "throttling", "load", "core", "starvation"],
                    "load": ["load average", "high load", "queue", "bottleneck"],
                    "memory": ["ram", "swap", "oom", "out of memory", "leak"]
                }
                
                keywords = symptom_registry.get(failing_service.lower(), [failing_service.lower()])
                search_term = f"alert_service: {failing_service} severity: {alert_status} keywords: {' '.join(keywords)} details: {alert_output}"
                print(f"[Context Orchestrator]: Optimized ChromaDB Search Term -> {search_term}")
            else:
                search_term = user_query if user_query else "high core utilization stress load performance anomaly bottleneck"

            context["chromadb"]["matched_incidents"] = vector_memory.query_semantic_context("incidents", search_term, n_results=1)
            
            target_coll = "remediation" if "remediation" in vector_memory.collections else "incident_ledger"
            if target_coll in vector_memory.collections:
                context["chromadb"]["matched_remediations"] = vector_memory.query_semantic_context(target_coll, search_term, n_results=1)

        # Predictive Machine Learning Inference Lookahead
        if intent in ["TREND_ANALYSIS", "ROOT_CAUSE"] or has_active_alerts:
            import bridge.main as core_app
            
            if hasattr(core_app, "ml_forecaster") and core_app.ml_forecaster is not None:
                try:
                    print("[Context Orchestrator]: Querying Prophet inference matrix for future horizons...")
                    
                    # Generate exact rolling minute timestamps relative to execution clock
                    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                    future_dates = pd.date_range(start=current_time, periods=self.default_lookahead, freq="min")
                    future_df = pd.DataFrame({'ds': future_dates})
                    
                    forecast_df = core_app.ml_forecaster.predict(future_df)
                    
                    context["machine_learning_forecast"] = {
                        "status": "active",
                        "target_host": host_filter,
                        "target_metric": "cpu_utilization",
                        "lookahead_window_minutes": self.default_lookahead,
                        "predictions": [
                            {
                                "timestamp": str(row["ds"]),
                                "predicted_value_baseline": round(float(row["yhat"]), 2),
                                "confidence_floor": round(float(row["yhat_lower"]), 2),
                                "confidence_ceiling": round(float(row["yhat_upper"]), 2)
                            }
                            for _, row in forecast_df.iterrows()
                        ]
                    }
                except Exception as ml_err:
                    print(f"[Context Orchestrator Warning]: Prophet projection sequence skipped: {ml_err}")
                    context["machine_learning_forecast"] = {"status": "error", "detail": str(ml_err)}
            else:
                print("[Context Orchestrator]: ML predictor is uninitialized in bridge.main. Skipping Layer 4 contexts.")
                context["machine_learning_forecast"] = {"status": "unavailable", "detail": "Model weights unallocated in RAM"}

        return context
    
orchestrator = ContextOrchestrator()