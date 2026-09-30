#!/usr/bin/env python3
"""Verifikasi setup proyek.

Fungsi:
- cek file penting ada / tidak
- cek env tidak kosong
- cek CSV minimal 1 baris
- cek leakage kolom 'Season'
- cek rolling first value NaN
- cek model bisa dimuat
- status final exit 0/1
"""

import os
import logging
import sys
import pandas as pd
import joblib
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    filename=os.path.join(ROOT, 'logs', 'verify_setup.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)


def check_files():
    """Cek file penting."""
    paths = {
        '.env': os.path.join(ROOT, '.env'),
        'matches_normalized.csv': os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv'),
        'model_1x2.pkl': os.path.join(ROOT, 'models', 'model_1x2.pkl'),
        'model_ou.pkl': os.path.join(ROOT, 'models', 'model_ou.pkl'),
        'model_btts.pkl': os.path.join(ROOT, 'models', 'model_btts.pkl'),
    }
    return {k: os.path.exists(v) for k, v in paths.items()}


def check_env():
    """Cek variabel API penting tidak kosong."""
    load_dotenv(os.path.join(ROOT, '.env'))
    api_key = os.getenv('API_KEY', '').strip()
    token = os.getenv('TELEGRAM_TOKEN', '').strip()
    return {'API_KEY': bool(api_key), 'TELEGRAM_TOKEN': bool(token)}


def check_csv(path):
    """Cek CSV ada minimal 1 baris."""
    if not os.path.exists(path):
        return False
    try:
        df = pd.read_csv(path)
        return len(df) >= 1
    except Exception:
        return False


def check_leakage(path):
    """Pastikan tidak ada kolom 'Season' dalam data utama."""
    if not os.path.exists(path):
        return False
    df = pd.read_csv(path)
    return 'Season' not in df.columns


def check_rolling_leakage(path):
    """Cek rolling features tidak mengandung NaN di baris pertama."""
    if not os.path.exists(path):
        return False
    df = pd.read_csv(path)
    for col in ['form_points_5', 'form_points_10', 'goals_for_avg_5', 'goals_against_avg_5', 'xg_avg_5', 'xga_avg_5', 'shots_avg_5', 'corners_avg_5']:
        if col in df.columns:
            if pd.isna(df[col].iloc[0]):
                return True
    return False


def check_models():
    """Muat 3 model untuk pengecekan validitas."""
    result = {}
    for name in ['model_1x2.pkl', 'model_ou.pkl', 'model_btts.pkl']:
        path = os.path.join(ROOT, 'models', name)
        result[name] = os.path.exists(path)
        if result[name]:
            try:
                joblib.load(path)
                result[name] = True
            except Exception:
                result[name] = False
    return result


def print_status(statuses):
    """Tampilkan status dalam tabel ringkas."""
    print('=== VERIFY SETUP ===')
    rows = []
    for key, value in statuses.items():
        rows.append([key, '✓' if value else '✗'])
    print(pd.DataFrame(rows, columns=['Item', 'Status']).to_markdown(index=False))


def main():
    """Entry point verifikasi setup."""
    file_status = check_files()
    env_status = check_env()
    csv_status = check_csv(os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv'))
    leak_status = check_leakage(os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv'))
    rolling_status = check_rolling_leakage(os.path.join(ROOT, 'data', 'processed', 'matches_features.csv'))
    model_status = check_models()

    combined = {
        **file_status,
        **{f'env_{k}': v for k, v in env_status.items()},
        'matches_normalized_has_rows': csv_status,
        'no_season_leakage': leak_status,
        'rolling_first_row_nan_ok': rolling_status,
        **{f'model_{k}': v for k, v in model_status.items()},
    }

    print_status(combined)
    failed = any(not value for value in combined.values())
    if failed:
        print('[ERR] Setup belum lengkap. Periksa file, .env, dan model.')
        return 1
    print('[OK] Setup valid dan siap dipakai.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
