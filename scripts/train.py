#!/usr/bin/env python3
"""Training model XGBoost untuk prediksi sepakbola.

Input: data/processed/matches_normalized.csv
Output:
- models/model_1x2.pkl (home/draw/away)
- models/model_ou.pkl (over/under 2.5)
- models/model_btts.pkl (both teams to score)

Validasi: time-based split 80/20, akurasi >80% = warning leakage.
"""

import os
import sys
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss, classification_report
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "processed" / "matches_normalized.csv"
MODEL_DIR = ROOT / "models"

FEATURES = [
    "xg_diff", "goal_diff", "form_points_5", "form_points_10",
    "home_goals_avg", "away_goals_avg", "home_win_rate", "away_win_rate",
    "h2h_avg_goals", "is_home", "xg_adjusted", "xga_adjusted",
    "goals_for_adjusted", "goals_against_adjusted", "rank_z"
]

logging.basicConfig(
    filename=ROOT / "logs" / "train.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def load_and_prepare_data():
    """Baca data, validasi kolom, siapkan untuk training."""
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"File input tidak ditemukan: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH)
    logging.info(f"Data loaded: {len(df)} rows, {len(df.columns)} columns")

    # Konversi date ke datetime dan sort
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # Ambil fitur yang tersedia
    available_features = [f for f in FEATURES if f in df.columns]
    missing_features = [f for f in FEATURES if f not in df.columns]

    if missing_features:
        print(f"[WARN] Fitur tidak tersedia: {missing_features}")
        logging.warning(f"Missing features: {missing_features}")

    # Siapkan target
    df["goals_for"] = df.get("goals_for", 0).fillna(0).astype(float)
    df["goals_against"] = df.get("goals_against", 0).fillna(0).astype(float)

    # Target 1: Hasil pertandingan (Home/Draw/Away)
    df["result"] = "Draw"
    df.loc[df["goals_for"] > df["goals_against"], "result"] = "Home"
    df.loc[df["goals_for"] < df["goals_against"], "result"] = "Away"

    # Target 2: Over/Under 2.5
    df["over_2_5"] = ((df["goals_for"] + df["goals_against"]) > 2.5).astype(int)

    # Target 3: BTTS (Both Teams To Score)
    df["btts"] = ((df["goals_for"] > 0) & (df["goals_against"] > 0)).astype(int)

    return df, available_features


def split_data_timebased(df, train_ratio=0.8):
    """Split data berdasarkan waktu (time-based), bukan random."""
    split_idx = int(len(df) * train_ratio)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    print(f"[INFO] Train: {len(train_df)} | Test: {len(test_df)}")
    return train_df, test_df


def train_model(X_train, y_train, model_type="binary"):
    """Train XGBoost model dengan parameter optimized."""
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        objective="multi:softprob" if model_type == "multiclass" else "binary:logistic",
        eval_metric="mlogloss" if model_type == "multiclass" else "logloss",
        verbosity=0,
    )
    model.fit(X_train, y_train, verbose=False)
    return model


def evaluate_model(model, X_test, y_test, model_name):
    """Evaluate model dengan metrics lengkap."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test) if hasattr(model, "predict_proba") else None

    acc = accuracy_score(y_test, y_pred)
    print(f"\n[METRIC] {model_name}: Accuracy = {acc:.4f}")

    if y_proba is not None:
        try:
            loss = log_loss(y_test, y_proba)
            print(f"[METRIC] {model_name}: Log Loss = {loss:.4f}")
        except Exception:
            print(f"[METRIC] {model_name}: Log Loss = N/A")

    print(f"\n[REPORT] {model_name}:")
    print(classification_report(y_test, y_pred, zero_division=0))

    if hasattr(model, "feature_importances_") and len(X_test.columns) > 0:
        importances = pd.Series(model.feature_importances_, index=X_test.columns)
        top10 = importances.sort_values(ascending=False).head(10)
        print(f"\n[TOP 10] Feature Importance ({model_name}):")
        for idx, (feat, val) in enumerate(top10.items(), 1):
            print(f"  {idx}. {feat}: {val:.4f}")

    if acc > 0.80:
        print(Fore.YELLOW + f"[WARN] Akurasi {acc:.2%} > 80%. Curiga LEAKAGE!")
        logging.warning(f"High accuracy detected ({acc:.2%}) for {model_name} - possible leakage")

    return acc


def save_model(model, path):
    """Simpan model ke pickle file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, str(path))
    print(f"[OK] Model saved: {path.relative_to(ROOT)}")
    logging.info(f"Model saved: {path}")


def main():
    """Orkestrasi training 3 model utama."""
    print("=== TRAINING MODEL ===")
    print("[INFO] Mempersiapkan data...")

    try:
        df, available_features = load_and_prepare_data()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        logging.error(f"Data loading failed: {exc}")
        return 1

    if not available_features:
        print("[ERROR] Tidak ada fitur yang tersedia untuk training.")
        return 1

    train_df, test_df = split_data_timebased(df, train_ratio=0.8)

    if len(train_df) == 0 or len(test_df) == 0:
        print("[ERROR] Split data tidak valid. Cek jumlah baris dalam CSV.")
        return 1

    X_train = train_df[available_features].fillna(0)
    X_test = test_df[available_features].fillna(0)

    # Model 1: 1X2 (Home/Draw/Away)
    print("\n[STEP 1/3] Training Model 1X2...")
    y_train_1x2 = train_df["result"].map({"Home": 0, "Draw": 1, "Away": 2}).fillna(1)
    y_test_1x2 = test_df["result"].map({"Home": 0, "Draw": 1, "Away": 2}).fillna(1)

    model_1x2 = train_model(X_train, y_train_1x2, model_type="multiclass")
    evaluate_model(model_1x2, X_test, y_test_1x2, "1X2")
    save_model(model_1x2, MODEL_DIR / "model_1x2.pkl")

    # Model 2: Over/Under 2.5
    print("\n[STEP 2/3] Training Model Over/Under 2.5...")
    y_train_ou = train_df["over_2_5"].fillna(0).astype(int)
    y_test_ou = test_df["over_2_5"].fillna(0).astype(int)

    model_ou = train_model(X_train, y_train_ou, model_type="binary")
    evaluate_model(model_ou, X_test, y_test_ou, "Over/Under 2.5")
    save_model(model_ou, MODEL_DIR / "model_ou.pkl")

    # Model 3: BTTS (Both Teams To Score)
    print("\n[STEP 3/3] Training Model BTTS...")
    y_train_btts = train_df["btts"].fillna(0).astype(int)
    y_test_btts = test_df["btts"].fillna(0).astype(int)

    model_btts = train_model(X_train, y_train_btts, model_type="binary")
    evaluate_model(model_btts, X_test, y_test_btts, "BTTS")
    save_model(model_btts, MODEL_DIR / "model_btts.pkl")

    print("\n" + "=" * 50)
    print("[OK] Semua 3 model berhasil dilatih dan disimpan.")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    from colorama import Fore, init
    init(autoreset=True)

    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Training dibatalkan oleh pengguna.")
        sys.exit(130)
    except Exception as exc:
        print(f"[ERROR] Unexpected error: {exc}")
        logging.exception("Unexpected error in train.py")
        sys.exit(1)
