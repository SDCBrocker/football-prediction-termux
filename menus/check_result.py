#!/usr/bin/env python3
"""Prediksi hari ini untuk pertandingan yang dipilih.

Input:
- 3 model (.pkl)
- data/raw/fixtures_today.csv

Output:
- data/processed/predictions_today.json
"""

import os
import json
import time
import pandas as pd
import numpy as np
import joblib
from dotenv import load_dotenv
from colorama import Fore, init

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, 'models')
FIXTURES_PATH = os.path.join(ROOT, 'data', 'raw', 'fixtures_today.csv')
OUTPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'predictions_today.json')

init(autoreset=True)


def load_models():
    """Muatt model terlatih."""
    return {
        '1x2': joblib.load(os.path.join(MODEL_DIR, 'model_1x2.pkl')),
        'ou': joblib.load(os.path.join(MODEL_DIR, 'model_ou.pkl')),
        'btts': joblib.load(os.path.join(MODEL_DIR, 'model_btts.pkl')),
    }


def load_fixtures(path=FIXTURES_PATH):
    """Baca fixtures hari ini."""
    if not os.path.exists(path):
        raise FileNotFoundError(f'Fixtures tidak ditemukan: {path}')
    return pd.read_csv(path)


def load_ou_lines():
    """Baca O/U lines dari .env dengan default 1.5, 2.5, 3.5."""
    load_dotenv(os.path.join(ROOT, '.env'))
    raw = os.getenv('OU_LINES', '1.5,2.5,3.5')
    return [float(x.strip()) for x in raw.split(',') if x.strip()]


def build_features(df):
    """Bangun fitur prediksi dari data historis. Ini tetap menerapkan fallback rata-rata liga bila tim baru."""
    if 'league' not in df.columns:
        raise ValueError('Kolom league dibutuhkan.')
    df = df.copy()
    if 'is_home' not in df.columns:
        df['is_home'] = 1
    if 'xg_diff' not in df.columns:
        df['xg_diff'] = df.get('xg', 0) - df.get('xga', 0)
    if 'goal_diff' not in df.columns:
        df['goal_diff'] = df.get('goals_for', 0) - df.get('goals_against', 0)
    if 'form_points_5' not in df.columns:
        df['form_points_5'] = 0
    if 'form_points_10' not in df.columns:
        df['form_points_10'] = 0
    if 'home_goals_avg' not in df.columns:
        df['home_goals_avg'] = 0
    if 'away_goals_avg' not in df.columns:
        df['away_goals_avg'] = 0
    if 'home_win_rate' not in df.columns:
        df['home_win_rate'] = 0.5
    if 'away_win_rate' not in df.columns:
        df['away_win_rate'] = 0.5
    if 'h2h_avg_goals' not in df.columns:
        df['h2h_avg_goals'] = 0
    if 'xg_adjusted' not in df.columns:
        df['xg_adjusted'] = df.get('xg', 0)
    if 'xga_adjusted' not in df.columns:
        df['xga_adjusted'] = df.get('xga', 0)
    if 'goals_for_adjusted' not in df.columns:
        df['goals_for_adjusted'] = df.get('goals_for', 0)
    if 'goals_against_adjusted' not in df.columns:
        df['goals_against_adjusted'] = df.get('goals_against', 0)
    if 'rank_z' not in df.columns:
        df['rank_z'] = 0
    return df


def predict_all(models, fixtures):
    """Prediksi 1X2, O/U dan BTTS untuk tiap match."""
    rows = []
    for _, match in fixtures.iterrows():
        row = {
            'match_id': match.get('match_id'),
            'league': match.get('league'),
            'home': match.get('home_team'),
            'away': match.get('away_team'),
            'predictions': [],
        }

        features = build_features(match.to_frame().T)
        X = features[[
            'xg_diff', 'goal_diff', 'form_points_5', 'form_points_10',
            'home_goals_avg', 'away_goals_avg', 'home_win_rate', 'away_win_rate',
            'h2h_avg_goals', 'is_home', 'xg_adjusted', 'xga_adjusted',
            'goals_for_adjusted', 'goals_against_adjusted', 'rank_z'
        ]].fillna(0)

        p1x2 = models['1x2'].predict_proba(X)[0]
        cls = models['1x2'].classes_
        idx_home = np.where(cls == 0)[0][0] if 0 in cls else 0
        idx_draw = np.where(cls == 1)[0][0] if 1 in cls else 0
        idx_away = np.where(cls == 2)[0][0] if 2 in cls else 0

        prediction_map = {
            'Home': p1x2[idx_home],
            'Draw': p1x2[idx_draw],
            'Away': p1x2[idx_away],
        }
        best_market = max(prediction_map, key=prediction_map.get)
        best_prob = prediction_map[best_market]
        odds = match.get('odds_home') if best_market == 'Home' else match.get('odds_draw') if best_market == 'Draw' else match.get('odds_away')
        value = (best_prob * odds) - 1

        row['predictions'].append({
            'market': '1X2',
            'prediction': best_market,
            'confidence': float(best_prob),
            'odds': float(odds) if pd.notna(odds) else 0.0,
            'value': float(value),
        })

        for line in load_ou_lines():
            over_prob = models['ou'].predict_proba(X)[0][1]
            row['predictions'].append({
                'market': f'O/U {line}',
                'prediction': 'Over' if over_prob >= 0.5 else 'Under',
                'confidence': float(max(over_prob, 1 - over_prob)),
                'odds': float(match.get(f'odds_over_{str(line).replace(".", "_"}')) if f'odds_over_{str(line).replace(".", "_" )}' in match else 0.0),
                'value': 0.0,
            })

        btts_prob = models['btts'].predict_proba(X)[0][1]
        btts_value = (btts_prob * match.get('odds_btts_yes', 0)) - 1
        row['predictions'].append({
            'market': 'BTTS',
            'prediction': 'Yes' if btts_prob >= 0.5 else 'No',
            'confidence': float(max(btts_prob, 1 - btts_prob)),
            'odds': float(match.get('odds_btts_yes', 0) if btts_prob >= 0.5 else match.get('odds_btts_no', 0)),
            'value': float(btts_value),
        })

        rows.append(row)

    return rows


def filter_recommendations(predictions):
    """Filter rekomendasi sesuai confidence dan value."""
    filtered = []
    min_conf = float(os.getenv('MIN_CONFIDENCE', '0.70'))
    min_value = float(os.getenv('MIN_VALUE', '0.05'))
    for match in predictions:
        selected = []
        for pred in match['predictions']:
            if pred.get('confidence', 0) >= min_conf and pred.get('value', 0) >= min_value:
                selected.append(pred)
        if selected:
            match['predictions'] = selected
            filtered.append(match)
    return filtered


def save_predictions(data, path=OUTPUT_PATH):
    """Simpan hasil prediksi ke JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def main():
    """Entry point prediksi hari ini."""
    print('=== PREDIKSI HARI INI ===')
    models = load_models()
    fixtures = load_fixtures()
    print(f'[INFO] Jumlah fixtures dibaca: {len(fixtures)}')
    predictions = predict_all(models, fixtures)
    filtered = filter_recommendations(predictions)
    save_predictions(filtered)
    print(f'[OK] Prediksi disimpan: {OUTPUT_PATH}')
    print(f'[INFO] Jumlah rekomendasi: {len(filtered)}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'[ERR] Error: {exc}')
