import numpy as np 
import pandas as pd 
from datetime import datetime, timedelta
import pickle

def load_model(model_path="er_load_model_enhanced.pkl"):
    with open(model_path, "rb") as f:
        return pickle.load(f)

def get_confidence_level(hour, load_level, day_of_week, contexts, base_mae):
    """
    Determine confidence level based on context
    
    Returns: 'high', 'medium', or 'low'
    """
    # Get context-specific MAE
    hour_mae = contexts['hour'].get(hour, base_mae)
    
    # Determine load level category
    if load_level <= 3:
        load_cat = 'low'
    elif load_level <= 6:
        load_cat = 'medium'
    elif load_level <= 10:
        load_cat = 'high'
    else:
        load_cat = 'extreme'
    
    load_mae = contexts['load_level'].get(load_cat, base_mae)
    dow_mae = contexts['day_of_week'].get(day_of_week, base_mae)
    
    # Average the context MAEs
    context_mae = (hour_mae + load_mae + dow_mae) / 3
    
    # Classify confidence
    if context_mae < base_mae * 0.85:
        return 'high', context_mae
    elif context_mae < base_mae * 1.15:
        return 'medium', context_mae
    else:
        return 'low', context_mae

def predict_next_hour_enhanced(recent_data, model_data, confidence_level='90%'):
    """
    Enhanced prediction with intervals and confidence
    
    Args:
        recent_data: DataFrame with 'timestamp' and 'count'
        model_data: Loaded model dictionary
        confidence_level: '90%', '95%', or '99%'
    
    Returns:
        dict with prediction, interval, and confidence
    """
    model = model_data['model']
    feature_cols = model_data['feature_cols']
    prediction_intervals = model_data['prediction_intervals']
    contexts = model_data['contexts']
    base_mae = model_data['test_mae']
    high_load_threshold = model_data['high_load_threshold']
    
    # Extract info
    last_timestamp = recent_data['timestamp'].iloc[-1]
    next_timestamp = last_timestamp + pd.Timedelta(hours=1)
    
    lag_1 = recent_data['count'].iloc[-1]
    lag_2 = recent_data['count'].iloc[-2]
    lag_3 = recent_data['count'].iloc[-3]
    
    # Create features
    features = {
        'lag_1': lag_1,
        'lag_2': lag_2,
        'lag_3': lag_3,
        'hour': next_timestamp.hour,
        'day_of_week': next_timestamp.dayofweek,
        'is_weekend': int(next_timestamp.dayofweek >= 5),
        'high_load_recent': int(lag_1 >= high_load_threshold)
    }
    
    # Optional features
    if 'is_evening_rush' in feature_cols:
        features['is_evening_rush'] = int(17 <= next_timestamp.hour <= 20)
    if 'is_night' in feature_cols:
        features['is_night'] = int(0 <= next_timestamp.hour <= 6)
    if 'avg_last_3h' in feature_cols:
        features['avg_last_3h'] = recent_data['count'].iloc[-3:].mean()
    if 'trend_last_3h' in feature_cols:
        features['trend_last_3h'] = lag_1 - lag_3
    if 'same_hour_yesterday' in feature_cols and len(recent_data) >= 24:
        features['same_hour_yesterday'] = recent_data['count'].iloc[-24]
    
    # Predict
    X_pred = pd.DataFrame([features])[feature_cols]
    # Predict (continuous)
    raw_prediction = max(0, model.predict(X_pred)[0])
    
    # Convert to integer count
    prediction = int(round(raw_prediction))
    
    # Prediction interval
    interval_width = prediction_intervals[confidence_level]
    lower_bound = max(0, int(round(raw_prediction - interval_width)))
    upper_bound = int(round(raw_prediction + interval_width))

    
    # Get confidence level
    confidence, context_mae = get_confidence_level(
        features['hour'],
        prediction,
        features['day_of_week'],
        contexts,
        base_mae
    )
    
    return {
       "predicted_arrivals": prediction,
        "range": [lower, upper],
        "confidence_level": confidence,

        "explanation_context": {
            "hour": features["hour"],
            "is_night": features.get("is_night", 0),
            "is_evening_rush": features.get("is_evening_rush", 0),
            "recent_trend": "increasing" if features.get("trend_last_3h", 0) > 0 else "decreasing",
            "high_load_recent": bool(features["high_load_recent"]),
        }
    }
