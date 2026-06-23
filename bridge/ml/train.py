import os
import joblib
import pandas as pd
import psycopg2
from prophet import Prophet
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

def extract_historical_metrics(days_horizon: int = 1) -> pd.DataFrame:
    """
    Connecting to TimescaleDB, queries historical metrics, and group them 
    into clean 5-minute operational blocks for optimal model training.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    load_dotenv(dotenv_path=root_dir / ".env")
    
    db_uri = os.getenv("TIMESCALE_DSN")
    if not db_uri:
        raise KeyError("[ML Ingestion Error]: TIMESCALE_DSN was not found. Verify your root .env file exists.")
        
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
    # 1. Pull the data
    data = extract_historical_metrics(days_horizon=1)
    
    if data.empty or len(data) < 5:
        print("[ML Error]: Training aborted. Insufficient metrics found.")
        return

    # 2. Add the physical saturation caps directly to the training dataframe
    data['cap'] = 100.0   # Maximum possible physical limit
    data['floor'] = 0.0   # Minimum possible physical limit

    os.makedirs("models", exist_ok=True)
    
    print("[ML Engine]: Initializing mathematical training sequence...")
    
    # 3. Initialize Prophet with 'logistic' growth
    model = Prophet(
        growth='logistic',           # Enforces the cap and floor boundaries
        changepoint_prior_scale=0.1, # Smooth out the trend adjustments
        yearly_seasonality=False, 
        weekly_seasonality=False, 
        daily_seasonality=True
    )
    
    model.fit(data)
    
    model_filename = "models/telemetry_forecaster.pkl"
    joblib.dump(model, model_filename)
    print(f"[ML Success]: Model weights saved to {model_filename}")

if __name__ == "__main__":
    execute_training_pipeline()