#!/usr/bin/env python3
"""Menu untuk mengecek hasil pertandingan yang sudah diprediksi.

Fungsi:
- load predictions_today.json
- match dengan matches_normalized.csv
- tampilkan tabel per pertandingan
- hitung akurasi hari ini
- simpan log untuk hari ini
"""

import os
import json
from datetime import datetime
import pandas as pd
from tabulate import tabulate
from colorama import Fore, init

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREDICTIONS_PATH = os.path.join(ROOT, 'data', 'processed', 'predictions_today.json')
MATCHES_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv')

init(autoreset=True)


def load_predictions(path=PREDICTIONS_PATH):
    """Baca file prediksi hari ini."""
    if not os.path.exists(path):
        raise FileNotFoundError(f'File prediksi tidak ditemukan: {path}')
    with open(path, 'r', encoding='utf-8') as file:
        return json.load(file)


def load_matches(path=MATCHES_PATH):
    """Baca dataset aktual untuk perbandingan hasil."""
    if not os.path.exists(path):
        raise FileNotFoundError(f'File matches_normalized.csv tidak ditemukan: {path}')
    return pd.read_csv(path)


def match_results(predictions, matches):
    """Cocokkan match_id dan menghitung status menang/kalah."""
    rows = []
    matches['match_id'] = matches['match_id'].astype(str)
    matches = matches.drop_duplicates(subset=['match_id'])
    for item in predictions:
        match_id = str(item.get('match_id'))
        selected = matches[matches['match_id'] == match_id]
        if selected.empty:
            continue
        actual = selected.iloc[0]
        home_goals = actual.get('goals_for', 0)
        away_goals = actual.get('goals_against', 0)
        if home_goals > away_goals:
            result = 'Home'
        elif home_goals < away_goals:
            result = 'Away'
        else:
            result = 'Draw'

        best_pred = item['predictions'][0]['prediction'] if item.get('predictions') else 'N/A'
        rows.append({
            'Match': f"{item.get('home')} vs {item.get('away')}",
            'Prediksi': best_pred,
            'Hasil': result,
            'Status': '✅' if best_pred == result else '❌',
        })
    return rows


def save_log(rows):
    """Simpan hasil evaluasi ke logs/check_result_YYYYMMDD.log."""
    log_dir = os.path.join(ROOT, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d')
    log_path = os.path.join(log_dir, f'check_result_{stamp}.log')
    with open(log_path, 'w', encoding='utf-8') as file:
        for row in rows:
            file.write(f"{row['Match']} | {row['Prediksi']} | {row['Hasil']} | {row['Status']}\n")
    return log_path


def main():
    """Entry point evaluasi hasil."""
    print('=== CEK RESULT ===')
    predictions = load_predictions()
    matches = load_matches()
    rows = match_results(predictions, matches)
    if not rows:
        print('[INFO] Tidak ada match yang cocok untuk dicek.')
        return 0

    print(tabulate(rows, headers='keys', tablefmt='grid'))
    accuracy = sum(1 for row in rows if row['Status'] == '✅') / len(rows)
    print(f'[INFO] Akurasi hari ini: {accuracy:.2%}')
    log_path = save_log(rows)
    print(f'[OK] Log disimpan: {log_path}')
    return accuracy


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'[ERR] Error: {exc}')
