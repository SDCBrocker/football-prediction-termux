#!/usr/bin/env python3
"""Backtest model untuk memvalidasi performa pada data test.

Output:
- logs/backtest_report.txt
- backtest_bankroll.png
- backtest_accuracy.png
"""

import os
import logging
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv')
MODEL_DIR = os.path.join(ROOT, 'models')
REPORT_PATH = os.path.join(ROOT, 'logs', 'backtest_report.txt')

logging.basicConfig(
    filename=os.path.join(ROOT, 'logs', 'backtest.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)


def load_models():
    """Muatt model hasil training."""
    return {
        '1x2': joblib.load(os.path.join(MODEL_DIR, 'model_1x2.pkl')),
        'ou': joblib.load(os.path.join(MODEL_DIR, 'model_ou.pkl')),
        'btts': joblib.load(os.path.join(MODEL_DIR, 'model_btts.pkl')),
    }


def load_test_data():
    """Baca 20% data terbaru untuk backtest."""
    df = pd.read_csv(DATA_PATH)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.sort_values('date').dropna(subset=['date']).reset_index(drop=True)
    split_idx = max(1, int(len(df) * 0.8))
    return df.iloc[split_idx:].copy()


def predict_all(models, df):
    """Lakukan prediksi untuk semua model."""
    preds = {}
    if 'xg_diff' in df.columns:
        X = df[['xg_diff', 'goal_diff', 'form_points_5', 'form_points_10',
                'home_goals_avg', 'away_goals_avg', 'home_win_rate', 'away_win_rate',
                'h2h_avg_goals', 'is_home', 'xg_adjusted', 'xga_adjusted',
                'goals_for_adjusted', 'goals_against_adjusted', 'rank_z']]
        preds['1x2'] = models['1x2'].predict(X)
        preds['ou'] = models['ou'].predict(X)
        preds['btts'] = models['btts'].predict(X)
    return preds


def accuracy_per_confidence(df, predictions):
    """Hitung akurasi per band confidence."""
    band = {
        '50-60%': (0.5, 0.6),
        '60-70%': (0.6, 0.7),
        '70-80%': (0.7, 0.8),
        '80%+': (0.8, 1.0),
    }
    report = {}
    for label, (low, high) in band.items():
        mask = (df.get('prediction_conf', 0.0) >= low) & (df.get('prediction_conf', 0.0) < high)
        if mask.any():
            report[label] = accuracy_score(df.loc[mask, 'actual'], df.loc[mask, 'prediction'])
        else:
            report[label] = np.nan
    return report


def value_betting_simulation(df):
    """Simulasi value betting berdasarkan odds dan probabilitas."""
    df = df.copy()
    df['value'] = (df['probability'] * df['odds']) - 1
    filtered = df[df['value'] > 0.05]
    roi = filtered['profit'].sum() / max(filtered['stake'].sum(), 1)
    return filtered, roi


def bankroll_simulation(df):
    """Simulasi bankroll 1 jt dengan stake 1% dan maksimal 3 leg."""
    bankroll = 1_000_000
    stake = bankroll * 0.01
    df = df.copy()
    df['stake'] = stake
    df['profit'] = np.where(df['actual'] == df['prediction'], df['stake'] * (df['odds'] - 1), -df['stake'])
    bankroll_series = [bankroll]
    for _, row in df.iterrows():
        bankroll = max(0, bankroll + row['profit'])
        bankroll_series.append(bankroll)
    return bankroll_series, df


def plot_results(bankroll_series, accuracy_report):
    """Buat grafik bankroll dan akurasi."""
    plt.figure(figsize=(12, 5))
    plt.plot(bankroll_series, color='green', linewidth=2)
    plt.title('Bankroll Simulation')
    plt.xlabel('Tahun / Periode')
    plt.ylabel('Bankroll')
    plt.tight_layout()
    plt.savefig(os.path.join(ROOT, 'backtest_bankroll.png'))
    plt.close()

    plt.figure(figsize=(10, 5))
    labels = list(accuracy_report.keys())
    values = [v for v in accuracy_report.values() if pd.notna(v)]
    plt.bar(labels[:len(values)], values, color='royalblue')
    plt.title('Accuracy by Confidence Band')
    plt.ylabel('Accuracy')
    plt.tight_layout()
    plt.savefig(os.path.join(ROOT, 'backtest_accuracy.png'))
    plt.close()


def save_report(report):
    """Simpan ringkasan backtest ke logs/backtest_report.txt."""
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as file:
        file.write(report)
    logging.info('Backtest report saved.')


def main():
    """Entry point backtest."""
    print('=== BACKTEST ===')
    models = load_models()
    df = load_test_data()
    preds = predict_all(models, df)
    print('[OK] Prediksi lengkap dibuat untuk data test.')

    accuracy_report = accuracy_per_confidence(df.assign(prediction=preds['1x2'], actual=df.get('result', 'Home')), {
        'prediction': preds['1x2']
    })
    bankroll_series, sim_df = bankroll_simulation(df.assign(prediction=preds['1x2'], actual=df.get('result', 'Home')).copy())
    plot_results(bankroll_series, accuracy_report)

    report = "Backtest Report\n"
    report += f"Accuracy by confidence: {accuracy_report}\n"
    report += f"Bankroll akhir: {bankroll_series[-1]:,.0f}\n"
    save_report(report)
    print(f'[OK] Laporan tersimpan: {REPORT_PATH}')
    print(f'[OK] Grafik tersimpan: {os.path.join(ROOT, "backtest_bankroll.png")}, {os.path.join(ROOT, "backtest_accuracy.png")}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.exception('Error pada backtest.py: %s', exc)
        print(f'[ERR] Error: {exc}')
