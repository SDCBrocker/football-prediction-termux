#!/usr/bin/env python3
"""Pembersihan data pertandingan.

Input: data/processed/matches_raw.csv
Output: data/processed/matches_clean.csv

Fungsi utama:
- membersihkan kolom leakage
- menangani missing values
- mengubah tanggal menjadi datetime
- menyortir dan menyimpan hasil
"""

import os
import logging
from datetime import datetime
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_raw.csv')
OUTPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_clean.csv')

logging.basicConfig(
    filename=os.path.join(ROOT, 'logs', 'clean.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)


def load_data(path):
    """Baca file CSV utama."""
    if not os.path.exists(path):
        raise FileNotFoundError(f'File tidak ditemukan: {path}')
    df = pd.read_csv(path)
    logging.info(f'Loaded data: {len(df)} baris dari {path}')
    return df


def drop_leakage_columns(df):
    """Buang kolom leakage yang berpotensi mengandung informasi masa depan."""
    leakage_patterns = [
        'SeasonPos', 'SeasonPoints', 'SeasonWin', 'SeasonDraw', 'SeasonLoss',
        'SeasonGF', 'SeasonGA', 'SeasonGD', 'final', 'end_position',
        'promoted', 'relegated'
    ]
    columns_to_drop = []
    for column in df.columns:
        lowered = str(column).lower()
        if any(pattern.lower() in lowered for pattern in leakage_patterns):
            columns_to_drop.append(column)
    df = df.drop(columns=columns_to_drop, errors='ignore')
    logging.info(f'Dropping leakage columns: {columns_to_drop}')
    return df


def handle_missing(df):
    """Hapus kolom/row dengan missing value berlebihan dan isi nilai default."""
    df = df.copy()
    max_missing_ratio = 0.5
    threshold = max(len(df) * max_missing_ratio, 1)
    df = df.dropna(axis=1, thresh=threshold)

    for col in df.columns:
        if df[col].dtype.kind in 'if':
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna('Unknown')
    logging.info('Missing values handled.')
    return df


def convert_date(df):
    """Konversi kolom tanggal ke datetime dan urutkan."""
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.sort_values('date').reset_index(drop=True)
        logging.info('Kolom date dikonversi ke datetime.')
    return df


def save_data(df, path):
    """Simpan CSV hasil pembersihan."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    logging.info(f'Data saved to {path}. Total rows: {len(df)}')


def main():
    """Orkestrasi pipeline clean data."""
    print('=== CLEAN DATA ===')
    df = load_data(INPUT_PATH)
    df = drop_leakage_columns(df)
    df = handle_missing(df)
    df = convert_date(df)
    save_data(df, OUTPUT_PATH)
    print(f'[OK] Data bersih disimpan: {OUTPUT_PATH}')
    print(f'[INFO] Total baris: {len(df)}')
    print(f'[INFO] Total kolom: {len(df.columns)}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.exception('Error pada clean_data: %s', exc)
        print(f'[ERR] Error: {exc}')
