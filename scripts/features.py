#!/usr/bin/env python3
"""Feature engineering untuk data pertandingan sepakbola.

Input: data/processed/matches_clean.csv
Output: data/processed/matches_features.csv

Fitur yang dibuat:
- Differential: goal_diff, xg_diff
- Rolling (per team, dengan shift(1)): form_points_5, goals_for_avg_5, dll
- Home/Away: home_goals_avg, away_goals_avg, home_win_rate, away_win_rate
- H2H: h2h_avg_goals, h2h_home_wins
- Contextual: is_home
"""

import os
import sys
import logging
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "processed" / "matches_clean.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "matches_features.csv"

logging.basicConfig(
    filename=ROOT / "logs" / "features.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def load_data(path):
    """Baca file CSV hasil cleaning."""
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {path}")
    df = pd.read_csv(path)
    logging.info(f"Data loaded: {len(df)} rows from {path}")
    return df


def create_differential_features(df):
    """Buat fitur selisih (differential)."""
    df = df.copy()
    df["goals_for"] = df.get("goals_for", 0).fillna(0).astype(float)
    df["goals_against"] = df.get("goals_against", 0).fillna(0).astype(float)
    df["xg"] = df.get("xg", 0).fillna(0).astype(float)
    df["xga"] = df.get("xga", 0).fillna(0).astype(float)

    df["goal_diff"] = df["goals_for"] - df["goals_against"]
    df["xg_diff"] = df["xg"] - df["xga"]
    return df


def create_rolling_features(df):
    """Buat rolling features grouped by team dengan shift(1) untuk menghindari leakage."""
    df = df.copy()

    if "team" not in df.columns:
        print("[WARN] Kolom 'team' tidak ada. Rolling features akan dilewati.")
        logging.warning("Column 'team' not found. Skipping rolling features.")
        return df

    # Pastikan kolom yang diperlukan ada
    for col in ["points", "goals_for", "goals_against", "xg", "xga", "shots", "corners"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0).astype(float)

    # Sort by team dan date
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values(["team", "date"]).reset_index(drop=True)

    # Rolling dengan shift(1) = hanya data historis, bukan masa depan
    df["form_points_5"] = df.groupby("team")["points"].transform(
        lambda s: s.rolling(window=5, min_periods=1).sum().shift(1)
    )
    df["form_points_10"] = df.groupby("team")["points"].transform(
        lambda s: s.rolling(window=10, min_periods=1).sum().shift(1)
    )
    df["goals_for_avg_5"] = df.groupby("team")["goals_for"].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df["goals_against_avg_5"] = df.groupby("team")["goals_against"].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df["xg_avg_5"] = df.groupby("team")["xg"].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df["xga_avg_5"] = df.groupby("team")["xga"].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df["shots_avg_5"] = df.groupby("team")["shots"].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )
    df["corners_avg_5"] = df.groupby("team")["corners"].transform(
        lambda s: s.rolling(window=5, min_periods=1).mean().shift(1)
    )

    # Fill NaN dari rolling (baris pertama)
    rolling_cols = [
        "form_points_5", "form_points_10", "goals_for_avg_5", "goals_against_avg_5",
        "xg_avg_5", "xga_avg_5", "shots_avg_5", "corners_avg_5"
    ]
    for col in rolling_cols:
        df[col] = df[col].fillna(0)

    logging.info("Rolling features created with shift(1).")
    return df


def create_home_away_features(df):
    """Buat fitur home/away berdasarkan rata-rata performa tim."""
    df = df.copy()

    if "team" not in df.columns:
        print("[WARN] Kolom 'team' tidak ada. Home/away features akan dilewati.")
        return df

    df["goals_for"] = df.get("goals_for", 0).fillna(0).astype(float)
    df["goals_against"] = df.get("goals_against", 0).fillna(0).astype(float)

    # Rata-rata goals per tim
    team_stats = df.groupby("team").agg(
        home_goals_avg=("goals_for", "mean"),
        away_goals_avg=("goals_against", "mean"),
    ).reset_index()

    df = df.merge(team_stats, on="team", how="left")
    df["home_goals_avg"] = df["home_goals_avg"].fillna(0)
    df["away_goals_avg"] = df["away_goals_avg"].fillna(0)

    # Win rate
    df["result"] = "Draw"
    df.loc[df["goals_for"] > df["goals_against"], "result"] = "Win"
    df.loc[df["goals_for"] < df["goals_against"], "result"] = "Loss"

    team_win_rate = df.groupby("team")["result"].apply(
        lambda x: (x == "Win").sum() / len(x) if len(x) > 0 else 0.5
    ).reset_index()
    team_win_rate.columns = ["team", "home_win_rate"]

    df = df.merge(team_win_rate, on="team", how="left")
    df["home_win_rate"] = df["home_win_rate"].fillna(0.5)
    df["away_win_rate"] = 1 - df["home_win_rate"]
    df["away_win_rate"] = df["away_win_rate"].fillna(0.5)

    logging.info("Home/away features created.")
    return df


def create_h2h_features(df):
    """Buat fitur head-to-head (H2H) antar tim."""
    df = df.copy()

    if "team" not in df.columns or "opponent" not in df.columns:
        print("[WARN] Kolom 'team' atau 'opponent' tidak ada. H2H features akan dilewati.")
        df["h2h_avg_goals"] = 0.0
        df["h2h_home_wins"] = 0.0
        return df

    df["goals_for"] = df.get("goals_for", 0).fillna(0).astype(float)
    df["is_home"] = df.get("is_home", 0).fillna(0).astype(int)

    # H2H stats
    h2h_stats = df.groupby(["team", "opponent"]).agg(
        h2h_avg_goals=("goals_for", "mean"),
        h2h_home_wins=("is_home", "mean"),
    ).reset_index()

    df = df.merge(h2h_stats, on=["team", "opponent"], how="left")
    df["h2h_avg_goals"] = df["h2h_avg_goals"].fillna(0)
    df["h2h_home_wins"] = df["h2h_home_wins"].fillna(0)

    logging.info("H2H features created.")
    return df


def create_contextual_features(df):
    """Buat fitur kontekstual (is_home)."""
    df = df.copy()
    df["is_home"] = df.get("is_home", 0).fillna(0).astype(int)
    return df


def save_data(df, path):
    """Simpan hasil feature engineering ke CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logging.info(f"Features saved to {path}. Rows: {len(df)}")


def main():
    """Orkestrasi pipeline feature engineering."""
    print("=== FEATURE ENGINEERING ===")

    try:
        df = load_data(INPUT_PATH)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        logging.error(f"Data loading failed: {exc}")
        return 1

    print("[STEP 1/5] Creating differential features...")
    df = create_differential_features(df)

    print("[STEP 2/5] Creating rolling features...")
    df = create_rolling_features(df)

    print("[STEP 3/5] Creating home/away features...")
    df = create_home_away_features(df)

    print("[STEP 4/5] Creating H2H features...")
    df = create_h2h_features(df)

    print("[STEP 5/5] Creating contextual features...")
    df = create_contextual_features(df)

    save_data(df, OUTPUT_PATH)

    new_features = [
        "goal_diff", "xg_diff", "form_points_5", "form_points_10",
        "goals_for_avg_5", "goals_against_avg_5", "xg_avg_5", "xga_avg_5",
        "shots_avg_5", "corners_avg_5", "home_goals_avg", "away_goals_avg",
        "home_win_rate", "away_win_rate", "h2h_avg_goals", "h2h_home_wins", "is_home"
    ]
    present = [col for col in new_features if col in df.columns]
    nan_total = df[present].isna().sum().sum() if present else 0

    print(f"\n[OK] Feature engineering selesai.")
    print(f"[INFO] Fitur baru dibuat: {present}")
    print(f"[INFO] Total NaN pada fitur baru: {nan_total}")
    print(f"[INFO] Output: {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Feature engineering dibatalkan.")
        sys.exit(130)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        logging.exception("Error in features.py")
        sys.exit(1)
