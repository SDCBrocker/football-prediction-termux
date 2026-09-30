#!/usr/bin/env python3
"""Normalisasi fitur sepakbola per liga.

Input: data/processed/matches_features.csv
Output: data/processed/matches_normalized.csv

Fitur yang dinormalisasi:
- xg, xga, goals_for, goals_against, shots, corners, fouls, rank

Fitur yang tidak dinormalisasi:
- possession, passes_accuracy, form_5, points_per_game
"""

import os
import logging
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_features.csv')
OUTPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv')

LEAGUE_COEF = {
    'EPL': 1.00,
    'LaLiga': 0.98,
    'SerieA': 0.96,
    'Bundesliga': 0.95,
    'Ligue1': 0.92,
    'Eredivisie': 0.85,
    'PrimeiraLiga': 0.84,
    'Championship': 0.80,
    'LigaMX': 0.78,
    'Brasileirao': 0.76,
}

COLS_TO_NORMALIZE = ['xg', 'xga', 'goals_for', 'goals_against', 'shots', 'corners', 'fouls', 'rank']

logging.basicConfig(
    filename=os.path.join(ROOT, 'logs', 'normalize.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)


def add_league_coef(df):
    """Tambahkan koefisien liga sebagai nilai multiplier."""
    df = df.copy()
    df['league_coef'] = df['league'].map(LEAGUE_COEF).fillna(1.0)
    return df


def zscore_per_league(df):
    """Z-score per liga untuk kolom yang ditentukan."""
    df = df.copy()
    for col in COLS_TO_NORMALIZE:
        if col in df.columns:
            mean = df.groupby(['league', 'season'])[col].transform('mean')
            std = df.groupby(['league', 'season'])[col].transform('std').replace(0, np.nan)
            df[f'{col}_z'] = (df[col] - mean) / std.replace(0, np.nan)
            df[f'{col}_z'] = df[f'{col}_z'].fillna(0)
    return df


def adjusted_features(df):
    """Buat fitur yang telah di-adjust berdasarkan league coeff."""
    df = df.copy()
    for col in COLS_TO_NORMALIZE:
        z_col = f'{col}_z'
        if z_col in df.columns:
            df[f'{col}_adjusted'] = df[z_col] * df['league_coef']
    return df


def save_data(df, path):
    """Simpan hasil normalisasi."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    logging.info(f'Normalized data saved to {path}. rows={len(df)}')


def main():
    """Orkestrasi normalisasi data."""
    print('=== NORMALISASI DATA ===')
    df = pd.read_csv(INPUT_PATH)
    df = add_league_coef(df)
    df = zscore_per_league(df)
    df = adjusted_features(df)
    save_data(df, OUTPUT_PATH)

    new_cols = [col for col in df.columns if 'adjusted' in col or '_z' in col or 'league_coef' in col]
    print(f'[OK] Kolom baru: {new_cols}')
    print('[INFO] Rata-rata per liga:')
    print(df.groupby('league')['league_coef'].mean().sort_values())


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.exception('Error pada normalize.py: %s', exc)
        print(f'[ERR] Error: {exc}')
