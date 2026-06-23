# train.py
import os
import joblib
import pandas as pd
import psycopg2
from prophet import Prophet
from datetime import datetime, timezone

def extract_historical_metrics(days_horizon: int = 1) -> pd.DataFrame:
    """
    Connecting to TimescaleDB, queries historical metrics, and group them 
    into clean 5-minute operational blocks for optimal model training.
    """
    db_uri = os.getenv("TIMESCALE_DSN")
    conn = psycopg2.connect(db_uri)
    
    query = f"""
    SELECT 
        time_bucket('5 minutes', "timestamp") AS ds,
        AVG(metric_value) AS y
    FROM metrics
    WHERE "timestamp" > NOW() - INTERVAL '{days_horizon} days'
      AND service = 'Cpu'
      AND metric_name = 'percentage_utilization'
    GROUP BY ds
    ORDER BY ds ASC;
    """
    
    print(f"[ML Ingestion]: Querying last {days_horizon} days of telemetry (5-min buckets)...")
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"[ML Ingestion]: Data pulled. Total training data steps: {len(df)}")
    
    if not df.empty and 'ds' in df.columns:
        df['ds'] = pd.to_datetime(df['ds']).dt.tz_localize(None)
        
    return df

def execute_training_pipeline():
    data = extract_historical_metrics(days_horizon=1)
    
    if data.empty or len(data) < 5:
        print("Training aborted. Insufficient metrics found matching the clean data schema.")
        return

    os.makedirs("models", exist_ok=True)
    
    print("Initializing mathematical training sequence for srv-prod-app-01 cpu...")
    
    model = Prophet(
        changepoint_prior_scale=0.5,
        yearly_seasonality=False, 
        weekly_seasonality=False, 
        daily_seasonality=True
    )
    
    model.fit(data)
    
    model_filename = "models/telemetry_forecaster.pkl"
    joblib.dump(model, model_filename)
    print(f"[ML Success]: Model weight matrix serialized and saved to {model_filename}")

if __name__ == "__main__":
    execute_training_pipeline()