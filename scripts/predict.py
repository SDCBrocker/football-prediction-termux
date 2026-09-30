#!/usr/bin/env python3
"""Prediksi hari ini untuk pertandingan yang dipilih.

Input:
- 3 model terlatih (.pkl)
- data/raw/fixtures_today.csv (format: match_id, league, home_team, away_team, odds_*)

Output:
- data/processed/predictions_today.json (rekomendasi dengan confidence & value)

Fitur:
- Multi-line O/U (1.5, 2.5, 3.5)
- BTTS (Yes/No)
- 1X2 (Home/Draw/Away)
- Filter: MIN_CONFIDENCE, MIN_VALUE
- Fallback: rata-rata liga untuk tim baru
"""

import os
import sys
import json
from pathlib import Path

import pandas as pd
import numpy as np
import joblib
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"
FIXTURES_PATH = ROOT / "data" / "raw" / "fixtures_today.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "predictions_today.json"

load_dotenv(ROOT / ".env")


def load_models():
    """Muat 3 model yang sudah dilatih."""
    models = {}
    for name in ["model_1x2.pkl", "model_ou.pkl", "model_btts.pkl"]:
        path = MODEL_DIR / name
        if not path.exists():
            raise FileNotFoundError(f"Model tidak ditemukan: {path}")
        models[name.replace(".pkl", "")] = joblib.load(str(path))
    return models


def load_fixtures(path=FIXTURES_PATH):
    """Baca fixtures hari ini dari CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Fixtures tidak ditemukan: {path}")
    return pd.read_csv(path)


def load_ou_lines():
    """Baca O/U lines dari .env (default: 1.5, 2.5, 3.5)."""
    raw = os.getenv("OU_LINES", "1.5,2.5,3.5")
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def load_env_params():
    """Baca parameter prediksi dari .env."""
    return {
        "min_confidence": float(os.getenv("MIN_CONFIDENCE", "0.70")),
        "min_value": float(os.getenv("MIN_VALUE", "0.05")),
    }


def build_features_for_match(match_row, features_list):
    """Bangun vektor fitur untuk satu pertandingan.

    Jika kolom tidak ada, gunakan default value (0 atau rata-rata).
    """
    features = {}
    for col in features_list:
        if col in match_row.index:
            val = match_row[col]
            features[col] = float(val) if pd.notna(val) else 0.0
        else:
            features[col] = 0.0
    return features


def predict_match(models, match_row, ou_lines, env_params):
    """Prediksi semua market untuk satu pertandingan."""
    FEATURE_LIST = [
        "xg_diff", "goal_diff", "form_points_5", "form_points_10",
        "home_goals_avg", "away_goals_avg", "home_win_rate", "away_win_rate",
        "h2h_avg_goals", "is_home", "xg_adjusted", "xga_adjusted",
        "goals_for_adjusted", "goals_against_adjusted", "rank_z"
    ]

    features_dict = build_features_for_match(match_row, FEATURE_LIST)
    X = pd.DataFrame([features_dict])

    predictions = []

    # 1X2
    try:
        model_1x2 = models["model_1x2"]
        proba_1x2 = model_1x2.predict_proba(X)[0]
        classes_1x2 = model_1x2.classes_

        # Cari kelas dengan prob tertinggi
        best_idx = np.argmax(proba_1x2)
        best_class = classes_1x2[best_idx] if best_idx < len(classes_1x2) else 0
        best_prob = float(proba_1x2[best_idx])

        # Map ke home/draw/away
        class_map = {0: "Home", 1: "Draw", 2: "Away"}
        prediction_label = class_map.get(best_class, "Draw")

        # Ambil odds
        odds_key_map = {"Home": "odds_home", "Draw": "odds_draw", "Away": "odds_away"}
        odds_key = odds_key_map.get(prediction_label, "odds_home")
        odds = float(match_row[odds_key]) if odds_key in match_row.index else 1.0

        value = (best_prob * odds) - 1
        predictions.append({
            "market": "1X2",
            "prediction": prediction_label,
            "confidence": best_prob,
            "odds": odds,
            "value": value,
        })
    except Exception as exc:
        print(f"[WARN] 1X2 prediction error: {exc}")

    # Over/Under lines
    try:
        model_ou = models["model_ou"]
        proba_ou = model_ou.predict_proba(X)[0]

        for line in ou_lines:
            over_prob = float(proba_ou[1]) if len(proba_ou) > 1 else 0.5
            prediction = "Over" if over_prob >= 0.5 else "Under"

            # Ambil odds
            line_str = str(line).replace(".", "_")
            if prediction == "Over":
                odds_key = f"odds_over_{line_str}"
            else:
                odds_key = f"odds_under_{line_str}"

            odds = float(match_row[odds_key]) if odds_key in match_row.index else 1.0
            value = (over_prob * odds) - 1

            predictions.append({
                "market": f"O/U {line}",
                "prediction": prediction,
                "confidence": max(over_prob, 1 - over_prob),
                "odds": odds,
                "value": value,
            })
    except Exception as exc:
        print(f"[WARN] O/U prediction error: {exc}")

    # BTTS
    try:
        model_btts = models["model_btts"]
        proba_btts = model_btts.predict_proba(X)[0]
        btts_prob = float(proba_btts[1]) if len(proba_btts) > 1 else 0.5

        prediction = "Yes" if btts_prob >= 0.5 else "No"
        odds_key = "odds_btts_yes" if prediction == "Yes" else "odds_btts_no"
        odds = float(match_row[odds_key]) if odds_key in match_row.index else 1.0
        value = (btts_prob * odds) - 1

        predictions.append({
            "market": "BTTS",
            "prediction": prediction,
            "confidence": max(btts_prob, 1 - btts_prob),
            "odds": odds,
            "value": value,
        })
    except Exception as exc:
        print(f"[WARN] BTTS prediction error: {exc}")

    return predictions


def filter_recommendations(all_predictions, env_params):
    """Filter rekomendasi berdasarkan confidence dan value minimum."""
    min_conf = env_params["min_confidence"]
    min_value = env_params["min_value"]

    filtered = []
    for match in all_predictions:
        selected_preds = [
            p for p in match["predictions"]
            if p["confidence"] >= min_conf and p["value"] >= min_value
        ]
        if selected_preds:
            match["predictions"] = selected_preds
            filtered.append(match)

    return filtered


def save_predictions(data, path=OUTPUT_PATH):
    """Simpan hasil prediksi ke JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    """Entry point prediksi hari ini."""
    print("=== PREDIKSI HARI INI ===")

    # Load models
    try:
        print("[INFO] Memuat model...")
        models = load_models()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 1

    # Load fixtures
    try:
        print("[INFO] Memuat fixtures hari ini...")
        fixtures = load_fixtures()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if fixtures.empty:
        print("[INFO] Tidak ada fixtures untuk hari ini.")
        return 0

    print(f"[INFO] Jumlah pertandingan: {len(fixtures)}")

    # Load parameters
    ou_lines = load_ou_lines()
    env_params = load_env_params()
    print(f"[INFO] O/U Lines: {ou_lines}")
    print(f"[INFO] Min Confidence: {env_params['min_confidence']:.0%}")
    print(f"[INFO] Min Value: {env_params['min_value']:.2%}")

    # Prediksi semua pertandingan
    all_predictions = []
    for idx, (_, match) in enumerate(fixtures.iterrows(), 1):
        match_id = match.get("match_id", f"unknown_{idx}")
        home = match.get("home_team", "Unknown")
        away = match.get("away_team", "Unknown")
        league = match.get("league", "Unknown")

        print(f"[{idx}/{len(fixtures)}] Predicting: {home} vs {away} ({league})")

        predictions = predict_match(models, match, ou_lines, env_params)
        all_predictions.append({
            "match_id": match_id,
            "league": league,
            "home": home,
            "away": away,
            "predictions": predictions,
        })

    # Filter dan simpan
    filtered = filter_recommendations(all_predictions, env_params)
    save_predictions(filtered)

    print(f"\n[OK] Prediksi selesai.")
    print(f"[INFO] Total pertandingan: {len(all_predictions)}")
    print(f"[INFO] Rekomendasi valid (confidence & value): {len(filtered)}")
    print(f"[INFO] Output: {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Prediksi dibatalkan.")
        sys.exit(130)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
