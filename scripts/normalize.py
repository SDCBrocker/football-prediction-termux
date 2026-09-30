#!/usr/bin/env python3
"""Feature engineering untuk data pertandingan.

Input: data/processed/matches_clean.csv
Output: data/processed/matches_features.csv

Fungsi utama:
- differential features
- rolling features dengan shift(1)
- home/away features
- h2h features
- contextual features
"""

import os
import logging
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_clean.csv')
OUTPUT_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_features.csv')

logging.basicConfig(
    filename=os.path.join(ROOT, 'logs', 'features.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
)


def create_differential_features(df):
    """Buat feature selisih gol dan xg."""
    df = df.copy()
    if 'goals_for' in df.columns and 'goals_against' in df.columns:
        df['goal_diff'] = df['goals_for'] - df['goals_against']
    else:
        df['goal_diff'] = 0

    if 'xg' in df.columns and 'xga' in df.columns:
        df['xg_diff'] = df['xg'] - df['xga']
    else:
        df['xg_diff'] = 0
    return df


def create_rolling_features(df):
    """Buat rolling features grouped by team, harus menggunakan shift(1)."""
    df = df.copy()
    if 'team' not in df.columns:
        raise ValueError('Kolom team dibutuhkan untuk rolling features.')

    if 'date' in df.columns:
        df = df.sort_values(['team', 'date']).reset_index(drop=True)

    df['form_points_5'] = df.groupby('team')['points'].transform(
        lambda s: s.rolling(window=5, min_periods=1).sum().shift(1)
    )
    df['form_points_10'] = df.groupby('team')['points'].transform(
        lambda s: s.rolling(window=10, min_periods=1).sum().shift(1)
    )
    df['goals_for_avg_5'] = df.groupby('team')['goals_for'].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df['goals_against_avg_5'] = df.groupby('team')['goals_against'].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df['xg_avg_5'] = df.groupby('team')['xg'].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df['xga_avg_5'] = df.groupby('team')['xga'].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df['shots_avg_5'] = df.groupby('team')['shots'].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df['corners_avg_5'] = df.groupby('team')['corners'].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )

    if df['form_points_5'].iloc[0] is not pd.isna(df['form_points_5'].iloc[0]):
        logging.warning('Baris pertama rolling tidak NaN. Periksa leakage atau urutan data.')
    return df


def create_home_away_features(df):
    """Buat feature home-away mencerminkan rata-rata performance tim."""
    df = df.copy()
    team_group = df.groupby('team')
    df['home_goals_avg'] = team_group['goals_for'].transform('mean')
    df['away_goals_avg'] = team_group['goals_against'].transform('mean')

    if 'result' in df.columns:
        home_win_rate = df.groupby('team')['result'].transform(
            lambda s: s.eq('Win').mean()
        )
        df['home_win_rate'] = home_win_rate
        df['away_win_rate'] = df.groupby('team')['result'].transform(
            lambda s: s.eq('Loss').mean()
        )
    else:
        df['home_win_rate'] = 0.5
        df['away_win_rate'] = 0.5
    return df


def create_h2h_features(df):
    """Buat feature rekor head-to-head."""
    df = df.copy()
    if {'team', 'opponent'}.issubset(df.columns):
        pair = df.groupby(['team', 'opponent']).agg(
            h2h_avg_goals=('goals_for', 'mean'),
            h2h_home_wins=('is_home', 'mean')
        ).reset_index()
        df = df.merge(pair, on=['team', 'opponent'], how='left')
    else:
        df['h2h_avg_goals'] = 0.0
        df['h2h_home_wins'] = 0.0
    return df


def create_contextual_features(df):
    """Buat feature kontekstual seperti status home/away."""
    df = df.copy()
    df['is_home'] = df.get('is_home', 0).fillna(0)
    return df


def save_data(df, path):
    """Simpan hasil feature engineering."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    logging.info(f'Data features saved: {path}, rows={len(df)}')


def main():
    """Pipeline feature engineering utama."""
    print('=== FEATURE ENGINEERING ===')
    df = pd.read_csv(INPUT_PATH)
    df = create_differential_features(df)
    df = create_rolling_features(df)
    df = create_home_away_features(df)
    df = create_h2h_features(df)
    df = create_contextual_features(df)
    save_data(df, OUTPUT_PATH)

    new_features = ['goal_diff', 'xg_diff', 'form_points_5', 'form_points_10',
                    'goals_for_avg_5', 'goals_against_avg_5', 'xg_avg_5',
                    'xga_avg_5', 'shots_avg_5', 'corners_avg_5',
                    'home_goals_avg', 'away_goals_avg', 'home_win_rate',
                    'away_win_rate', 'h2h_avg_goals', 'h2h_home_wins', 'is_home']
    present = [col for col in new_features if col in df.columns]
    nan_count = df[present].isna().sum().sum() if present else 0
    print(f'[OK] Fitur baru dibuat: {present}')
    print(f'[INFO] Total NaN pada fitur baru: {nan_count}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.exception('Error pada features.py: %s', exc)
        print(f'[ERR] Error: {exc}')
