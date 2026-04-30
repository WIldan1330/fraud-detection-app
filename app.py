from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import joblib
import pandas as pd
import numpy as np
import os
import traceback

app = Flask(__name__)
CORS(app)

# ============================
# ROUTES FRONTEND
# ============================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/cek")
def cek():
    return render_template("cek.html")

# ============================
# ROUTE API INFO
# ============================

@app.route("/api")
def home():
    return jsonify({
        "message": "API Deteksi Fraud Aktif",
        "endpoints": [
            "/predict_pca_csv",
            "/predict_raw_csv",
            "/predict_manual"
        ]
    })


# ============================
# CONFIG PATH
# ============================

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

MODEL_PATH           = os.path.join(MODELS_DIR, "rf_model.pkl")
SCALER_PATH          = os.path.join(MODELS_DIR, "scaler.pkl")
FEATURE_COLUMNS_PATH = os.path.join(MODELS_DIR, "feature_columns.pkl")

THRESHOLD = 0.25


# ============================
# LOAD MODEL
# ============================

def load_artifact(path, name):
    try:
        obj = joblib.load(path)
        print(f"Loaded: {name}")
        return obj
    except Exception as e:
        print(f"Failed loading {name}: {e}")
        return None


model           = load_artifact(MODEL_PATH, "RandomForest Model")
scaler          = load_artifact(SCALER_PATH, "Scaler")
feature_columns = load_artifact(FEATURE_COLUMNS_PATH, "Feature Columns")


# ============================
# HELPER
# ============================

def choose_id_column(df):
    possible_ids = [
        "TransactionID",
        "transaction_id",
        "id",
        "AccountNumber",
        "account"
    ]
    for col in possible_ids:
        if col in df.columns:
            return col
    return None


def sanitize_number(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).strip()
        if cleaned.count('.') > 1:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
        return float(cleaned)
    except:
        return 0.0


def adjust_risk(prob, amount):
    prob = float(prob or 0.0)
    amount = sanitize_number(amount)

    if amount >= 50_000_000:
        base = 0.85
    elif amount >= 20_000_000:
        base = 0.65
    elif amount >= 10_000_000:
        base = 0.45
    else:
        base = None

    if base is not None:
        noise = np.random.uniform(-0.07, 0.07)
        prob = max(prob, round(min(base + noise, 0.99), 4))

    return prob


# ============================
# PCA CSV
# ============================

@app.route("/predict_pca_csv", methods=["POST"])
def predict_pca_csv():
    if "file" not in request.files:
        return jsonify({"error": "Upload CSV"}), 400

    try:
        df = pd.read_csv(request.files["file"])

        missing = [col for col in feature_columns if col not in df.columns]
        if missing:
            return jsonify({"error": "Kolom tidak sesuai", "missing": missing}), 400

        df_final = df[feature_columns]
        probs = model.predict_proba(df_final)[:, 1]
        preds = (probs >= THRESHOLD).astype(int)

        id_col = choose_id_column(df)

        results = []
        for i in range(len(df)):
            tx_id = df[id_col].iloc[i] if id_col else i
            results.append({
                "transaction_id": int(tx_id),
                "fraud_probability": float(probs[i]),
                "status": "Fraud" if preds[i] else "Sah"
            })

        return jsonify({"results": results})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============================
# RAW CSV
# ============================

@app.route("/predict_raw_csv", methods=["POST"])
def predict_raw_csv():
    if "file" not in request.files:
        return jsonify({"error": "Upload CSV"}), 400

    try:
        df = pd.read_csv(request.files["file"])

        if "Amount" not in df.columns or "Time" not in df.columns:
            return jsonify({"error": "Butuh kolom Amount & Time"}), 400

        KURS = 15000
        df["Amount"] = df["Amount"] / KURS

        scaled = scaler.transform(df[["Amount", "Time"]])
        df["scaled_Amount"] = scaled[:, 0]
        df["scaled_Time"] = scaled[:, 1]

        df["Amount_IDR"] = df["Amount"] * KURS

        for col in feature_columns:
            if col not in df.columns:
                df[col] = 0

        df_final = df[feature_columns]
        probs = model.predict_proba(df_final)[:, 1]

        for i in range(len(df)):
            probs[i] = adjust_risk(probs[i], df["Amount_IDR"].iloc[i])

        results = []
        id_col = choose_id_column(df)

        for i in range(len(df)):
            tx_id = df[id_col].iloc[i] if id_col else i
            results.append({
                "transaction_id": int(tx_id),
                "amount": float(df["Amount_IDR"].iloc[i]),
                "fraud_probability": float(probs[i]),
                "status": "Fraud" if probs[i] >= THRESHOLD else "Sah"
            })

        return jsonify({"results": results})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============================
# MANUAL INPUT
# ============================

@app.route("/predict_manual", methods=["POST"])
def predict_manual():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Data kosong"}), 400

        amount = sanitize_number(data.get("Amount"))
        time = sanitize_number(data.get("Time"))

        KURS = 15000
        amount_usd = amount / KURS

        df = pd.DataFrame([data])
        df["Amount"] = amount_usd
        df["Time"] = time

        scaled = scaler.transform(df[["Amount", "Time"]])
        df["scaled_Amount"] = scaled[:, 0]
        df["scaled_Time"] = scaled[:, 1]

        for col in feature_columns:
            if col not in df.columns:
                df[col] = 0

        df_final = df[feature_columns]

        prob = model.predict_proba(df_final)[0][1]
        prob = adjust_risk(prob, amount)

        return jsonify({
            "fraud_probability": float(prob),
            "status": "Fraud" if prob >= THRESHOLD else "Sah"
        })

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============================
# RUN
# ============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)