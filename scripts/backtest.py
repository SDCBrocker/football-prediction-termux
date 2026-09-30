#!/usr/bin/env python3
"""Training model prediksi sepakbola.

Input: data/processed/matches_normalized.csv
Output:
- models/model_1x2.pkl
- models/model_ou.pkl
- models/model_btts.pkl

Model yang dilatih:
- 1X2: hasil akhir (home/draw/away)
- O/U 2.5: over/under
- BTTS: yes/no
"""

import os
import logging
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss, classification_report
from xgboost import XGBClassifier

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv')
MODEL_DIR = os.path.join(ROOT, 'models')

FEATURES = [
    'xg_diff', 'goal_diff', 'form_points_5', 'form_points_10',
    'home_goals_avg', 'away_goals_avg', 'home_win_rate', 'away_win_rate',
    'h2h_avg_goals', 'is_home', 'xg_adjusted', 'xga_adjusted',
    'goals_for_adjusted', 'goals_against_adjusted', 'rank_z'
]

logging.basicConfig(
    filename=os.path.join(ROOT, 'logs', 'train.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)


def split_data(df):
    """Split data secara time-based 80/20 (terbaru sebagai test)."""
    df = df.sort_values('date').reset_index(drop=True)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    return train_df, test_df


def prepare_target(df, target_name):
    """Siapkan target untuk model."""
    if target_name == 'result':
        mapping = {'Home': 0, 'Draw': 1, 'Away': 2}
        return df[target_name].map(mapping).fillna(1)

    if target_name == 'over_2_5':
        total_goals = df.get('home_goals', 0) + df.get('away_goals', 0)
        return (total_goals > 2.5).astype(int)

    if target_name == 'btts':
        return ((df.get('home_goals', 0) > 0) & (df.get('away_goals', 0) > 0)).astype(int)

    return df[target_name].astype(int)


def train_model(X_train, y_train, model_name):
    """Latih model XGBoost dengan setting tertentu."""
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        objective='multi:softprob' if model_name == 'result' else 'binary:logistic',
        eval_metric='mlogloss' if model_name == 'result' else 'logloss',
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test, target_name):
    """Evaluasi model: akurasi, log_loss, classification report, feature importance."""
    pred = model.predict(X_test)
    acc = accuracy_score(y_test, pred)
    try:
        loss = log_loss(y_test, model.predict_proba(X_test))
    except Exception:
        loss = None

    print(f'\n[METRIK] {target_name}: accuracy={acc:.4f}, log_loss={loss}')
    print(classification_report(y_test, pred, zero_division=0))

    if hasattr(model, 'feature_importances_'):
        importances = pd.Series(model.feature_importances_, index=X_test.columns)
        top10 = importances.sort_values(ascending=False).head(10)
        print('[TOP10] Fitur terpenting:')
        print(top10)

    if acc > 0.80:
        logging.warning('Akurasi > 80%, kemungkinan leakage. Cek pipeline dan validasi data.')
        print('[WARN] Akurasi >80%. Curiga leakage. Cek pipeline dan retrain bila perlu.')

    return acc, loss


def save_model(model, path):
    """Simpan model ke file pickle."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)
    logging.info(f'Model saved: {path}')


def main():
    """Train 3 model utama untuk prediksi."""
    print('=== TRAIN MODEL ===')
    df = pd.read_csv(INPUT_PATH)
    available = [col for col in FEATURES if col in df.columns]
    missing = [col for col in FEATURES if col not in df.columns]
    if missing:
        print(f'[WARN] Fitur tidak ditemukan: {missing}')

    df = df[available].copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date').reset_index(drop=True)

    df['result'] = np.where(df.get('goals_for', 0) > df.get('goals_against', 0), 'Home',
                            np.where(df.get('goals_for', 0) < df.get('goals_against', 0), 'Away', 'Draw'))
    df['over_2_5'] = (df.get('goals_for', 0) + df.get('goals_against', 0) > 2.5).astype(int)
    df['btts'] = ((df.get('goals_for', 0) > 0) & (df.get('goals_against', 0) > 0)).astype(int)

    train_df, test_df = split_data(df)

    for target_name, model_name, filename in [
        ('result', 'result', 'model_1x2.pkl'),
        ('over_2_5', 'over_2_5', 'model_ou.pkl'),
        ('btts', 'btts', 'model_btts.pkl'),
    ]:
        X_train = train_df[available]
        X_test = test_df[available]
        y_train = prepare_target(train_df, target_name)
        y_test = prepare_target(test_df, target_name)

        model = train_model(X_train, y_train, model_name)
        evaluate_model(model, X_test, y_test, target_name)
        save_model(model, os.path.join(MODEL_DIR, filename))

    print('[OK] Semua model berhasil dilatih dan disimpan di folder models/.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.exception('Error pada train.py: %s', exc)
        print(f'[ERR] Error: {exc}')
