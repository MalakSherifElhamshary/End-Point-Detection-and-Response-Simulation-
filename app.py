import os
import joblib
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import Dense, TimeDistributed
import tensorflow as tf
from datetime import datetime
import csv
import warnings
warnings.filterwarnings("ignore")

# ============================================
# Flask App Initialization
# ============================================
app = Flask(__name__)

# ============================================
# Fix for loading model with quantization_config issue
# ============================================
class PatchedDense(Dense):
    """Custom Dense layer that ignores 'quantization_config' argument."""
    def __init__(self, *args, **kwargs):
        kwargs.pop('quantization_config', None)
        super().__init__(*args, **kwargs)

class PatchedTimeDistributed(TimeDistributed):
    """Custom TimeDistributed layer that passes kwargs correctly."""
    def __init__(self, *args, **kwargs):
        kwargs.pop('quantization_config', None)
        super().__init__(*args, **kwargs)

# Register custom objects
custom_objects = {
    'Dense': PatchedDense,
    'TimeDistributed': PatchedTimeDistributed
}

# ============================================
# Load Model and Auxiliary Files
# ============================================
MODELS_DIR = "models"  # folder containing model files

if not os.path.exists(MODELS_DIR):
    raise FileNotFoundError(f"Folder '{MODELS_DIR}' not found. Make sure it exists with required files.")

# Load model with custom objects to ignore quantization_config
autoencoder = load_model(
    os.path.join(MODELS_DIR, "lstm_autoencoder.h5"),
    compile=False,
    custom_objects=custom_objects
)
print("✅ Model loaded successfully.")

# Load scaler
scaler = joblib.load(os.path.join(MODELS_DIR, "scaler.pkl"))
print("✅ Scaler loaded.")

# Load encoders
encoders = joblib.load(os.path.join(MODELS_DIR, "encoders.pkl"))
print("✅ Encoders loaded.")

# Load threshold
threshold = np.load(os.path.join(MODELS_DIR, "threshold.npy"))
print(f"✅ Threshold loaded: {threshold:.6f}")

# Load feature columns
with open(os.path.join(MODELS_DIR, "feature_cols.txt"), "r") as f:
    feature_cols = f.read().splitlines()
print(f"✅ Feature columns loaded: {feature_cols}")

# ============================================
# Temporary buffer for last 10 events per computer
# ============================================
event_buffer = {}

# ============================================
# Logging setup: store all predictions in a CSV file
# ============================================
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, "predictions_log.csv")

# Create CSV with headers if not exists
if not os.path.isfile(log_file):
    with open(log_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "computer", "event_time", "level", "source", "message",
            "buffer_length", "status", "mse", "threshold", "is_anomaly"
        ])

def log_prediction(computer, event, buffer_length, status, mse=None, is_anomaly=None):
    """Append a prediction record to the CSV log file."""
    with open(log_file, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            computer,
            event.get('timestamp', ''),
            event.get('level', ''),
            event.get('source', ''),
            event.get('message', ''),
            buffer_length,
            status,
            f"{mse:.6f}" if mse is not None else "",
            f"{threshold:.6f}",
            "1" if is_anomaly else ("0" if is_anomaly is False else "")
        ])

# ============================================
# Helper Functions
# ============================================
def extract_features(event):
    """Convert event dict to feature vector."""
    try:
        ts = pd.to_datetime(event['timestamp'])
    except Exception as e:
        raise ValueError(f"Invalid timestamp format: {event['timestamp']}") from e

    source_val = event.get('source', '')
    try:
        source_enc = encoders['source'].transform([source_val])[0]
    except ValueError:
        source_enc = -1
        print(f"⚠️ Warning: unknown source '{source_val}', using -1.")

    level_val = event.get('level', '')
    try:
        level_enc = encoders['level'].transform([level_val])[0]
    except ValueError:
        level_enc = -1
        print(f"⚠️ Warning: unknown level '{level_val}', using -1.")

    message = event.get('message', '')
    msg_length = len(message)
    word_count = len(message.split())
    has_error = 1 if any(k in message.lower() for k in ['error', 'fail', 'exception']) else 0

    features_dict = {
        'hour': ts.hour,
        'day_of_week': ts.dayofweek,
        'minute': ts.minute,
        'source_encoded': source_enc,
        'level_encoded': level_enc,
        'msg_length': msg_length,
        'word_count': word_count,
        'has_error': has_error
    }

    feature_vector = [features_dict[col] for col in feature_cols]
    return np.array(feature_vector, dtype=np.float32)

def check_anomaly(computer, features, event):
    """Add features to buffer, predict anomaly if buffer full, and log."""
    if computer not in event_buffer:
        event_buffer[computer] = []

    buffer = event_buffer[computer]
    buffer.append(features)
    if len(buffer) > 10:
        buffer.pop(0)

    result = {
        "is_anomaly": None,
        "mse": None,
        "threshold": float(threshold),
        "buffer_length": len(buffer),
        "remaining": 10 - len(buffer) if len(buffer) < 10 else 0
    }

    status = "buffering"
    is_anomaly_flag = None
    mse_val = None

    if len(buffer) == 10:
        sequence = np.array(buffer)
        sequence_scaled = scaler.transform(sequence)
        sequence_input = np.expand_dims(sequence_scaled, axis=0)

        reconstruction = autoencoder.predict(sequence_input, verbose=0)
        mse_val = np.mean(np.square(sequence_scaled - reconstruction))
        is_anomaly_flag = bool(mse_val > threshold)

        result["is_anomaly"] = is_anomaly_flag
        result["mse"] = float(mse_val)
        status = "anomaly" if is_anomaly_flag else "normal"

    log_prediction(computer, event, len(buffer), status, mse_val, is_anomaly_flag)
    return result, status

# ============================================
# Endpoints
# ============================================
@app.route('/event', methods=['POST'])
def receive_event():
    """Receive an event from the Agent."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON received"}), 400

    computer = data.get('computer')
    if not computer:
        return jsonify({"error": "Computer name is required"}), 400

    event = {
        'timestamp': data.get('timestamp'),
        'level': data.get('level'),
        'source': data.get('source'),
        'message': data.get('message', '')
    }

    if not event['timestamp']:
        return jsonify({"error": "Timestamp is required"}), 400

    try:
        features = extract_features(event)
    except Exception as e:
        return jsonify({"error": f"Feature extraction failed: {str(e)}"}), 400

    result, status = check_anomaly(computer, features, event)

    response = {
        "computer": computer,
        "timestamp": event['timestamp'],
        "status": status,
        "buffer_length": result["buffer_length"]
    }

    if result["mse"] is not None:
        response["mse"] = result["mse"]
        response["threshold"] = result["threshold"]

    if status == "anomaly":
        print(f"🚨 Anomaly detected on {computer} at {event['timestamp']} (MSE={result['mse']:.6f})")
        return jsonify(response), 202
    else:
        return jsonify(response), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "buffered_computers": list(event_buffer.keys()),
        "threshold": float(threshold)
    })

@app.route('/reset/<computer>', methods=['POST'])
def reset_buffer(computer):
    """Reset buffer for a specific computer (for testing)."""
    if computer in event_buffer:
        del event_buffer[computer]
        return jsonify({"message": f"Buffer cleared for {computer}"}), 200
    else:
        return jsonify({"error": f"Computer {computer} not found"}), 404

# ============================================
# Run the app
# ============================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)