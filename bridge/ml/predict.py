import os
import joblib
import json
import pandas as pd
from datetime import datetime, timezone

def generate_hourly_prediction_json():
    """
    Loading the trained Prophet weights matrix, dynamically anchoring the 
    timeline to the current host runtime execution clock, and outputs 
    a 60-minute prediction array spaced in 5-minute step blocks.
    """
    
    model_filename = "models/telemetry_forecaster.pkl"
    if not os.path.exists(model_filename):
        return json.dumps({
            "status": "error",
            "message": f"Model binary weight file not found at {model_filename}. Run train.py first."
        }, indent=2)
        
    print(f"Loading serialized model matrix: {model_filename}")
    model = joblib.load(model_filename)
    
    current_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    
    #Generates a 60-minute lookahead window at 5-minute intervals 
    future_timestamps = pd.date_range(start=current_time, periods=13, freq='5min')
    future = pd.DataFrame({'ds': future_timestamps})
    
    future['ds'] = future['ds'].dt.tz_localize(None)
    
    print("Executing linear regression trend projection across the 1-hour horizon...")
    forecast = model.predict(future)
    
    payload = {
        "status": "active",
        "target_host": "srv-prod-app-01",
        "target_metric": "cpu_utilization",
        "lookahead_window_minutes": 60,
        "step_size_minutes": 5,
        "generated_at": current_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "predictions": []
    }
    
    for _, row in forecast.iterrows():
        payload["predictions"].append({
            "timestamp": row['ds'].strftime('%Y-%m-%d %H:%M:%S'),
            "predicted_value_baseline": round(float(row['yhat']), 2),
            "confidence_floor": round(float(row['yhat_lower']), 2),
            "confidence_ceiling": round(float(row['yhat_upper']), 2)
        })
        
    return json.dumps(payload, indent=2)

if __name__ == "__main__":
    json_output = generate_hourly_prediction_json()
    print(json_output)