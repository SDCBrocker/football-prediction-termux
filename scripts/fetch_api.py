#!/usr/bin/env python3
"""Fetch data pertandingan dari OpenFootAPI dengan cache dan rate limiting.

Input:
- .env: API_KEY, LEAGUES, SEASONS
- Cache: 24 jam per liga-musim

Output:
- data/raw/cache/*.json (cache per liga-musim)
- data/processed/matches_raw.csv (hasil final)
- data/raw/quota.json (sisa quota API)

Rate Limit:
- Sleep 2 detik antar request (aman untuk free tier)
- Cache 24 jam mengurangi request
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
log_path = ROOT / "logs" / "fetch_api.log"
log_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

load_dotenv(ROOT / ".env")

API_BASE = "https://api.openownership.org/v1"
API_KEY = os.getenv("API_KEY", "")
CAGE_PATH = os.getenv("CAGE_PATH", "")

LEAGUES = os.getenv("LEAGUES", "EPL,LaLiga,SerieA,Bundesliga").split(",")
SEASONS = os.getenv("SEASONS", "2024,2025").split(",")

CACHE_DIR = ROOT / "data" / "raw" / "cache"
RAW_PATH = ROOT / "data" / "processed" / "matches_raw.csv"
QUOTA_PATH = ROOT / "data" / "raw" / "quota.json"

COLUMN_MAPPING = {
    'expected_goals': 'xg',
    'expected_goals_against': 'xga',
    'expected_goals_for': 'xg',
    'shots_on_goal': 'shots_on_target',
    'shots_on_target': 'shots_on_target',
    'total_shots': 'shots',
    'ball_possession': 'possession',
    'possession': 'possession',
    'corner_kicks': 'corners',
    'corners': 'corners',
    'fouls': 'fouls',
    'yellow_cards': 'yellow_cards',
    'red_cards': 'red_cards',
    'passes_accurate': 'passes_accuracy',
    'pass_accuracy': 'passes_accuracy',
    'passes_accuracy': 'passes_accuracy',
}

DEFAULT_STATS_COLS = [
    'match_id', 'shots', 'shots_on_target', 'possession',
    'corners', 'fouls', 'yellow_cards', 'red_cards',
    'passes_accuracy', 'xg', 'xga'
]


def fetch_api(endpoint, params=None):
    """Fetch data dari OpenFootAPI dengan error handling."""
    if params is None:
        params = {}

    params['apikey'] = API_KEY
    url = f"{API_BASE}{endpoint}"

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        logging.error(f"API request failed: {exc}")
        print(f"[ERROR] API request failed: {exc}")
        return None


def load_cache(league, season):
    """Muat cache dari file, validasi age dan format."""
    cache_path = CACHE_DIR / f"{league}_{season}.json"

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as file:
            cache_data = json.load(file)
    except json.JSONDecodeError:
        print(f"[WARN] Cache korup: {cache_path}, dihapus.")
        try:
            os.remove(cache_path)
        except OSError:
            pass
        return None
    except IOError as exc:
        print(f"[WARN] Gagal baca cache: {exc}")
        return None

    timestamp = cache_data.get('timestamp')
    if timestamp is None:
        return None

    try:
        age_hours = (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() / 3600
    except (ValueError, TypeError):
        return None

    if age_hours < 24:
        return cache_data.get('data')
    return None


def save_cache(league, season, data):
    """Simpan data ke cache dengan timestamp."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{league}_{season}.json"

    cache_data = {
        'timestamp': datetime.now().isoformat(),
        'league': league,
        'season': season,
        'data': data,
    }

    try:
        with open(cache_path, 'w', encoding='utf-8') as file:
            json.dump(cache_data, file, ensure_ascii=False, indent=2)
    except IOError as exc:
        logging.warning(f"Gagal simpan cache: {exc}")


def fetch_fixtures(league, season):
    """Fetch fixtures (pertandingan) untuk liga dan musim."""
    # Coba cache dulu
    cached = load_cache(f"{league}_{season}", "fixtures")
    if cached:
        print(f"[CACHE] Fixtures {league} {season} dari cache.")
        return cached

    print(f"[API] Fetch fixtures {league} {season}...")
    data = fetch_api("/fixtures", {"league": league, "season": season})

    if data and "fixtures" in data:
        save_cache(f"{league}_{season}", "fixtures", data["fixtures"])
        time.sleep(2)  # rate limit aman
        return data["fixtures"]

    return []


def fetch_standings(league, season):
    """Fetch standings (peringkat) untuk liga dan musim."""
    # Coba cache
    cached = load_cache(f"{league}_{season}", "standings")
    if cached:
        print(f"[CACHE] Standings {league} {season} dari cache.")
        return cached

    print(f"[API] Fetch standings {league} {season}...")
    data = fetch_api("/standings", {"league": league, "season": season})

    if data and "standings" in data:
        save_cache(f"{league}_{season}", "standings", data["standings"])
        time.sleep(2)
        return data["standings"]

    return []


def fetch_stats(match_id):
    """Fetch statistik untuk satu pertandingan."""
    print(f"[API] Fetch stats untuk match {match_id}...")
    data = fetch_api(f"/matches/{match_id}/statistics", {})

    rows = []
    if data and "statistics" in data:
        for stat_block in data["statistics"]:
            row = {"match_id": match_id}
            if "statistics" in stat_block:
                for stat in stat_block["statistics"]:
                    key = stat.get("type", "").lower()
                    value = stat.get("value")
                    if value is not None:
                        row[key] = value

            # Mapping kolom ke nama standar
            row = {COLUMN_MAPPING.get(k.lower(), k): v for k, v in row.items()}
            rows.append(row)

    time.sleep(2)  # rate limit

    if not rows:
        return pd.DataFrame(columns=DEFAULT_STATS_COLS)

    df_stats = pd.DataFrame(rows)
    for col in DEFAULT_STATS_COLS:
        if col not in df_stats.columns:
            df_stats[col] = None
    return df_stats[DEFAULT_STATS_COLS]


def build_match_rows(fixtures_list, standings_list, league, season):
    """Transform fixtures menjadi 2 baris per pertandingan (home + away)."""
    rows = []

    for fixture in fixtures_list:
        match_id = fixture.get("id")
        status = fixture.get("status")
        date = fixture.get("date")
        home_team = fixture.get("home", {}).get("name", "Unknown")
        away_team = fixture.get("away", {}).get("name", "Unknown")

        # Ambil skor jika pertandingan sudah selesai
        goals_for = None
        goals_against = None
        if status in ["FT", "AET", "PEN"]:
            score = fixture.get("score", {})
            goals_for = score.get("fulltime", {}).get("home")
            goals_against = score.get("fulltime", {}).get("away")

        # Baris 1: Home team
        rows.append({
            "match_id": match_id,
            "date": date,
            "league": league,
            "season": season,
            "team": home_team,
            "opponent": away_team,
            "is_home": 1,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "status": status,
        })

        # Baris 2: Away team
        if goals_for is not None and goals_against is not None:
            rows.append({
                "match_id": match_id,
                "date": date,
                "league": league,
                "season": season,
                "team": away_team,
                "opponent": home_team,
                "is_home": 0,
                "goals_for": goals_against,
                "goals_against": goals_for,
                "status": status,
            })

    df_main = pd.DataFrame(rows) if rows else pd.DataFrame()

    # Merge standings
    if standings_list and not df_main.empty:
        standings_rows = []
        for team_data in standings_list:
            standings_rows.append({
                "team": team_data.get("team", {}).get("name", ""),
                "league": league,
                "season": season,
                "rank": team_data.get("rank"),
                "points": team_data.get("points"),
                "points_per_game": team_data.get("goalsDiff") / max(team_data.get("played", 1), 1),
                "form": team_data.get("form"),
            })

        standings = pd.DataFrame(standings_rows)
        if not standings.empty:
            standings = standings.copy()
            standings['team'] = standings['team'].astype(str)
            df_main['team'] = df_main['team'].astype(str)
            standings = standings.drop_duplicates(
                subset=['team', 'league', 'season'], keep='first'
            )
            df_main = df_main.merge(
                standings[['team', 'league', 'season', 'rank', 'points',
                          'points_per_game', 'form']],
                on=['team', 'league', 'season'],
                how='left',
                suffixes=('', '_stand')
            )

    return df_main


def commit_update(df_main, df_new):
    """Gabungkan main dan new, sort by date, simpan ke CSV."""
    if df_main is None or df_main.empty:
        final_df = df_new.copy()
    else:
        all_cols = sorted(set(df_main.columns) | set(df_new.columns))
        df_main = df_main.reindex(columns=all_cols)
        df_new = df_new.reindex(columns=all_cols)
        final_df = pd.concat([df_main, df_new], ignore_index=True)

    if 'date' in final_df.columns:
        final_df['date'] = pd.to_datetime(final_df['date'], errors='coerce')
        final_df = final_df.sort_values('date').reset_index(drop=True)

    os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)
    final_df.to_csv(RAW_PATH, index=False)
    return final_df


def save_quota(remaining):
    """Simpan sisa quota ke file JSON."""
    quota_data = {
        'timestamp': datetime.now().isoformat(),
        'remaining': remaining,
    }
    os.makedirs(os.path.dirname(QUOTA_PATH), exist_ok=True)
    try:
        with open(QUOTA_PATH, 'w', encoding='utf-8') as f:
            json.dump(quota_data, f, ensure_ascii=False, indent=2)
    except IOError as exc:
        logging.warning(f"Gagal simpan quota: {exc}")


def main():
    """Entry point: fetch semua fixtures + standings + stats."""
    print("=== FETCH API ===")
    print(f"[INFO] API Key: {('*' * (len(API_KEY) - 4) + API_KEY[-4:]) if API_KEY else 'NOT SET'}")
    print(f"[INFO] Leagues: {LEAGUES}")
    print(f"[INFO] Seasons: {SEASONS}")

    if not API_KEY:
        print("[ERROR] API_KEY tidak diatur di .env")
        logging.error("API_KEY not configured")
        return 1

    df_main = None
    try:
        df_main = pd.read_csv(RAW_PATH)
    except FileNotFoundError:
        pass

    df_all_new = pd.DataFrame()

    for league in LEAGUES:
        for season in SEASONS:
            print(f"\n[LEAGUE] {league} / {season}")

            fixtures = fetch_fixtures(league, season)
            standings = fetch_standings(league, season)

            if not fixtures:
                print(f"[WARN] Tidak ada fixtures untuk {league} {season}")
                continue

            df_matches = build_match_rows(fixtures, standings, league, season)

            if df_matches.empty:
                print(f"[WARN] DataFrame kosong untuk {league} {season}")
                continue

            df_all_new = pd.concat([df_all_new, df_matches], ignore_index=True)
            print(f"[OK] {len(df_matches)} baris ditambahkan.")

    if df_all_new.empty:
        print("\n[WARN] Tidak ada data baru.")
        return 0

    print(f"\n[STEP] Commit update ke {RAW_PATH}...")
    df_final = commit_update(df_main, df_all_new)
    print(f"[OK] Total rows: {len(df_final)}")

    # Quota
    quota_path = os.path.join(ROOT, 'data', 'raw', 'quota.json')
    if os.path.exists(quota_path):
        try:
            with open(quota_path, 'r', encoding='utf-8') as f:
                quota_data = json.load(f)
            print(f"[INFO] Quota remaining: {quota_data.get('remaining', 'unknown')}")
        except (json.JSONDecodeError, IOError):
            print("[INFO] Quota: file tidak bisa dibaca")
    else:
        print("[INFO] Quota: belum tersedia")

    logging.info(f"Fetch completed. Total rows: {len(df_final)}")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[INFO] Fetch dibatalkan oleh pengguna.")
        sys.exit(130)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        logging.exception("Unexpected error in fetch_api.py")
        sys.exit(1)
