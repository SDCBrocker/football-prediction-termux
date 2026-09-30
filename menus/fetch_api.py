#!/usr/bin/env python3
"""Modul fetch data dari OpenFootAPI untuk Termux.

Fungsi utama:
- membaca env
- cache API dengan TTL 24 jam
- fetch fixtures, stats, standings, odds
- validasi, deduplikasi, backup, dan commit ke CSV utama

Semua komentar dan log diberikan dalam bahasa Indonesia agar mudah dipahami.
"""

import os
import sys
import json
import time
import hashlib
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CACHE_DIR = os.path.join(ROOT, 'data', 'raw', 'cache')
RAW_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_raw.csv')
BACKUP_DIR = os.path.join(ROOT, 'data', 'backup')


def load_env():
    """Muat variabel lingkungan API dan konfigurasi liga.

    Returns:
        dict: berisi API_KEY, API_BASE_URL, LEAGUES, SEASONS.
    """
    load_dotenv(os.path.join(ROOT, '.env'))
    api_key = os.getenv('API_KEY', '').strip()
    api_base_url = os.getenv('API_BASE_URL', 'https://api.openfootapi.com/v1').strip()
    leagues = [item.strip() for item in os.getenv('LEAGUES', 'EPL').split(',') if item.strip()]
    seasons = [item.strip() for item in os.getenv('SEASONS', '2024').split(',') if item.strip()]
    return {
        'API_KEY': api_key,
        'API_BASE_URL': api_base_url.rstrip('/'),
        'LEAGUES': leagues,
        'SEASONS': seasons,
    }


def get_cache_path(endpoint, params):
    """Buat nama file cache berdasarkan endpoint dan parameter."""
    payload = json.dumps(params, sort_keys=True)
    digest = hashlib.md5(f"{endpoint}|{payload}".encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{endpoint.replace('/', '_')}_{digest}.json")


def load_cache(endpoint, params):
    """Baca cache jika masih valid dalam 24 jam."""
    cache_path = get_cache_path(endpoint, params)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r', encoding='utf-8') as file:
            cache_data = json.load(file)
        timestamp = cache_data.get('timestamp')
        if timestamp is None:
            return None

        age_hours = (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() / 3600
        if age_hours < 24:
            return cache_data.get('data')
    except Exception:
        return None

    return None


def save_cache(endpoint, params, data):
    """Simpan cache hasil API ke file JSON."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = get_cache_path(endpoint, params)
    payload = {
        'timestamp': datetime.now().isoformat(),
        'data': data,
    }
    with open(cache_path, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def fetch_api(endpoint, params):
    """Ambil data dari API OpenFootAPI dan simpan cache serta quota."""
    env = load_env()
    api_key = env.get('API_KEY')
    base_url = env.get('API_BASE_URL')
    if not api_key:
        raise ValueError('API_KEY belum diisi. Silakan cek file .env.')

    cached = load_cache(endpoint, params)
    if cached is not None:
        print(f"[CACHE] Menggunakan cache untuk endpoint: {endpoint}")
        return cached

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json',
    }

    url = f"{base_url}{endpoint}"
    response = None
    retry_count = 0
    max_retries = 5

    while retry_count < max_retries:
        try:
            time.sleep(4)  # rate limit: 15 req/menit
            response = requests.get(url, headers=headers, params=params, timeout=60)

            if response.status_code == 200:
                data = response.json()
                save_cache(endpoint, params, data)
                quota = response.headers.get('x-ratelimit-remaining') or response.headers.get('X-RateLimit-Remaining')
                if quota is not None:
                    with open(os.path.join(ROOT, 'data', 'raw', 'quota.json'), 'w', encoding='utf-8') as f:
                        json.dump({'remaining': quota, 'timestamp': datetime.now().isoformat()}, f)
                return data

            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', '10'))
                print(f"[WARN] Rate limit terdeteksi. Menunggu {retry_after} detik...")
                time.sleep(retry_after)
                retry_count += 1
                continue

            if response.status_code == 401:
                raise PermissionError('401 Unauthorized: API key tidak valid.')

            if response.status_code == 404:
                print(f"[SKIP] Endpoint {endpoint} tidak ditemukan, di-skip.")
                return []

            if response.status_code >= 500:
                print(f"[WARN] Server error {response.status_code}, retry ke-{retry_count + 1}")
                time.sleep(5)
                retry_count += 1
                continue

            raise RuntimeError(f"Request gagal: {response.status_code} - {response.text[:200]}")
        except requests.RequestException as exc:
            print(f"[ERR] Request error: {exc}")
            retry_count += 1
            if retry_count >= max_retries:
                raise

    return []


def extract_list(payload):
    """Normalisasi payload API ke list."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ['response', 'data', 'matches', 'standings', 'teams', 'odds']:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return list(payload.values())
    return []


def fetch_fixtures(league, season):
    """Ambil fixture untuk liga dan musim tertentu."""
    params = {'league': league, 'season': season}
    data = fetch_api('/matches', params)
    rows = []
    for item in extract_list(data):
        try:
            match = item.get('fixture', {}) if isinstance(item, dict) else {}
            teams = item.get('teams', {}) if isinstance(item, dict) else {}
            goals = item.get('goals', {}) if isinstance(item, dict) else {}
            home_team = teams.get('home', {}).get('name') if isinstance(teams.get('home'), dict) else None
            away_team = teams.get('away', {}).get('name') if isinstance(teams.get('away'), dict) else None
            row = {
                'match_id': match.get('id') or item.get('id'),
                'league': league,
                'season': season,
                'date': match.get('date'),
                'home_team': home_team,
                'away_team': away_team,
                'home_goals': goals.get('home'),
                'away_goals': goals.get('away'),
                'status': match.get('status', {}).get('short') if isinstance(match.get('status'), dict) else None,
            }
            rows.append(row)
        except Exception:
            continue
    return pd.DataFrame(rows)


def fetch_stats(match_id):
    """Ambil stats per match id."""
    data = fetch_api(f'/matches/{match_id}/stats', {})
    rows = []
    for item in extract_list(data):
        if isinstance(item, dict):
            stat_map = item.get('statistics', []) or item.get('stats', []) or []
            row = {'match_id': match_id}
            for stat in stat_map:
                if not isinstance(stat, dict):
                    continue
                name = stat.get('type') or stat.get('name')
                val = stat.get('value')
                if name is not None:
                    row[name.lower().replace(' ', '_')] = val
            rows.append(row)
    if not rows:
        return pd.DataFrame(columns=[
            'match_id', 'shots', 'shots_on_target', 'possession', 'corners', 'fouls',
            'yellow_cards', 'red_cards', 'passes_accuracy', 'xg', 'xga'
        ])
    return pd.DataFrame(rows)


def fetch_standings(league, season):
    """Ambil klasemen liga untuk musim tertentu."""
    params = {'league': league, 'season': season}
    data = fetch_api('/standings', params)
    rows = []
    for item in extract_list(data):
        if not isinstance(item, dict):
            continue
        league_data = item.get('league', {}) if isinstance(item.get('league'), dict) else {}
        standings = league_data.get('standings', []) if isinstance(league_data, dict) else []
        for standing in standings:
            if not isinstance(standing, list):
                continue
            for team_row in standing:
                if not isinstance(team_row, dict):
                    continue
                team = team_row.get('team', {}).get('name') if isinstance(team_row.get('team'), dict) else None
                rows.append({
                    'league': league,
                    'season': season,
                    'team': team,
                    'rank': team_row.get('rank'),
                    'points': team_row.get('points'),
                    'form': team_row.get('form'),
                    'points_per_game': team_row.get('points_per_game'),
                })
    return pd.DataFrame(rows)


def fetch_odds(match_id):
    """Ambil odds pertandingan per match_id."""
    data = fetch_api(f'/matches/{match_id}/odds', {})
    rows = []
    for item in extract_list(data):
        if not isinstance(item, dict):
            continue
        bookmakers = item.get('bookmakers', [])
        for bookmaker in bookmakers:
            if not isinstance(bookmaker, dict):
                continue
            for market in bookmaker.get('markets', []):
                if not isinstance(market, dict):
                    continue
                if market.get('name') not in ['Match Winner', 'Over/Under', 'Both Teams To Score']:
                    continue
                for outcome in market.get('outcomes', []):
                    if not isinstance(outcome, dict):
                        continue
                    label = outcome.get('name')
                    odd = outcome.get('odd')
                    if label is not None and odd is not None:
                        rows.append({
                            'match_id': match_id,
                            'label': label,
                            'odd': odd,
                        })
    if not rows:
        return pd.DataFrame(columns=[
            'match_id', 'odds_home', 'odds_draw', 'odds_away',
            'odds_over_1_5', 'odds_under_1_5', 'odds_over_2_5',
            'odds_under_2_5', 'odds_over_3_5', 'odds_under_3_5',
            'odds_btts_yes', 'odds_btts_no'
        ])

    odds_map = {row['match_id']: {} for row in rows}
    for row in rows:
        odds_map[row['match_id']][row['label']] = row['odd']

    final = []
    for match_id_val, odd_map in odds_map.items():
        final.append({
            'match_id': match_id_val,
            'odds_home': odd_map.get('Home'),
            'odds_draw': odd_map.get('Draw'),
            'odds_away': odd_map.get('Away'),
            'odds_over_1_5': odd_map.get('Over 1.5'),
            'odds_under_1_5': odd_map.get('Under 1.5'),
            'odds_over_2_5': odd_map.get('Over 2.5'),
            'odds_under_2_5': odd_map.get('Under 2.5'),
            'odds_over_3_5': odd_map.get('Over 3.5'),
            'odds_under_3_5': odd_map.get('Under 3.5'),
            'odds_btts_yes': odd_map.get('Yes'),
            'odds_btts_no': odd_map.get('No'),
        })
    return pd.DataFrame(final)


def build_match_rows(fixtures, stats, standings, odds):
    """Gabungkan semua data dan buat 2 baris per laga (home & away)."""
    if fixtures.empty:
        return pd.DataFrame(columns=['match_id', 'league', 'season', 'date', 'team', 'opponent', 'is_home', 'goals_for', 'goals_against'])

    result_rows = []
    for _, row in fixtures.iterrows():
        match_id = row.get('match_id')
        league = row.get('league')
        season = row.get('season')
        date = row.get('date')
        home_team = row.get('home_team')
        away_team = row.get('away_team')
        home_goals = row.get('home_goals')
        away_goals = row.get('away_goals')

        pair = {
            'match_id': match_id,
            'league': league,
            'season': season,
            'date': date,
            'team': home_team,
            'opponent': away_team,
            'is_home': 1,
            'goals_for': home_goals,
            'goals_against': away_goals,
            'team_goals': home_goals,
            'opp_goals': away_goals,
        }
        result_rows.append(pair)

        pair2 = {
            'match_id': match_id,
            'league': league,
            'season': season,
            'date': date,
            'team': away_team,
            'opponent': home_team,
            'is_home': 0,
            'goals_for': away_goals,
            'goals_against': home_goals,
            'team_goals': away_goals,
            'opp_goals': home_goals,
        }
        result_rows.append(pair2)

    df_main = pd.DataFrame(result_rows)

    if not stats.empty:
        stats = stats.copy()
        stats['match_id'] = stats['match_id'].astype(str)
        df_main['match_id'] = df_main['match_id'].astype(str)
        df_main = df_main.merge(stats, on='match_id', how='left')

    if not standings.empty:
        standings = standings.copy()
        standings['team'] = standings['team'].astype(str)
        df_main['team'] = df_main['team'].astype(str)
        df_main = df_main.merge(standings[['team', 'league', 'season', 'rank', 'points', 'points_per_game', 'form']],
                                on=['team', 'league', 'season'], how='left', suffixes=('', '_stand'))

    if not odds.empty:
        odds = odds.copy()
        odds['match_id'] = odds['match_id'].astype(str)
        match_odds = df_main[['match_id', 'team']].drop_duplicates().merge(odds, on='match_id', how='left')
        df_main = df_main.merge(match_odds, on=['match_id', 'team'], how='left')

    return df_main


def validate_data(df):
    """Cek kolom wajib dan duplikat internal match_id."""
    required_cols = ['match_id', 'league', 'date', 'team', 'opponent']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f'Kolom wajib tidak ada: {missing}')

    if df.empty:
        return False

    id_series = df['match_id'].astype(str)
    if id_series.duplicated().any():
        raise ValueError('Terdapat duplikat match_id internal dalam data baru.')

    return True


def deduplicate(df_main, df_new):
    """Hapus duplikasi berdasarkan match_id."""
    if df_main.empty:
        return df_new
    df_main = df_main.copy()
    df_new = df_new.copy()
    df_main['match_id'] = df_main['match_id'].astype(str)
    df_new['match_id'] = df_new['match_id'].astype(str)
    existing = set(df_main['match_id'].unique())
    df_new = df_new[~df_new['match_id'].isin(existing)]
    return df_new


def backup_database():
    """Buat backup CSV utama ke folder data/backup."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(RAW_PATH):
        return None

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'matches_raw_{stamp}.csv')
    with open(RAW_PATH, 'rb') as src, open(backup_path, 'wb') as dst:
        dst.write(src.read())
    return backup_path


def commit_update(df_main, df_new):
    """Gabungkan main dan new, sort by date, simpan ke CSV."""
    if df_main is None or df_main.empty:
        final_df = df_new.copy()
    else:
        final_df = pd.concat([df_main, df_new], ignore_index=True)

    if 'date' in final_df.columns:
        final_df['date'] = pd.to_datetime(final_df['date'], errors='coerce')
        final_df = final_df.sort_values('date').reset_index(drop=True)

    os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)
    final_df.to_csv(RAW_PATH, index=False)
    return final_df


def main():
    """Entry point CLI fetch data API."""
    print('=== FETCH DATA DARI API OPENFOOT ===')
    env = load_env()
    league_filter = None
    season_filter = None
    all_flag = False
    update_flag = False

    args = sys.argv[1:]
    for i in range(len(args)):
        arg = args[i]
        if arg == '--league' and i + 1 < len(args):
            league_filter = args[i + 1]
        elif arg == '--season' and i + 1 < len(args):
            season_filter = args[i + 1]
        elif arg == '--all':
            all_flag = True
        elif arg == '--update':
            update_flag = True

    if not os.path.exists(os.path.dirname(RAW_PATH)):
        os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)

    if os.path.exists(RAW_PATH):
        df_main = pd.read_csv(RAW_PATH)
    else:
        df_main = pd.DataFrame()

    if all_flag:
        leagues = env['LEAGUES']
        seasons = env['SEASONS']
        combined = []
        for league in leagues:
            for season in seasons:
                print(f"\n[PROGRESS] Fetch league={league} season={season}")
                fixtures = fetch_fixtures(league, season)
                if fixtures.empty:
                    continue
                stats = pd.DataFrame()
                odds = pd.DataFrame()
                standings = fetch_standings(league, season)
                for match_id in fixtures['match_id'].dropna().astype(str).unique():
                    stats_df = fetch_stats(match_id)
                    odds_df = fetch_odds(match_id)
                    if not stats_df.empty:
                        stats = pd.concat([stats, stats_df], ignore_index=True)
                    if not odds_df.empty:
                        odds = pd.concat([odds, odds_df], ignore_index=True)
                built = build_match_rows(fixtures, stats, standings, odds)
                combined.append(built)
        if combined:
            df_new = pd.concat(combined, ignore_index=True)
        else:
            df_new = pd.DataFrame()
    elif league_filter and season_filter:
        print(f"[INFO] Fetch liga {league_filter}, musim {season_filter}")
        fixtures = fetch_fixtures(league_filter, season_filter)
        standings = fetch_standings(league_filter, season_filter)
        stats = pd.DataFrame()
        odds = pd.DataFrame()

        for match_id in fixtures['match_id'].dropna().astype(str).unique():
            stats_df = fetch_stats(match_id)
            odds_df = fetch_odds(match_id)
            if not stats_df.empty:
                stats = pd.concat([stats, stats_df], ignore_index=True)
            if not odds_df.empty:
                odds = pd.concat([odds, odds_df], ignore_index=True)

        df_new = build_match_rows(fixtures, stats, standings, odds)
    else:
        print('[INFO] Tidak ada filter liga/musim. Gunakan --league dan --season atau --all.')
        return 0

    if df_new.empty:
        print('[INFO] Tidak ada data baru yang di-fetch.')
        return 0

    validate_data(df_new)
    new_unique = deduplicate(df_main, df_new)
    print(f"[INFO] Data baru: {len(new_unique)} baris setelah deduplikasi.")

    if update_flag:
        backup = backup_database()
        print(f"[INFO] Backup: {backup}")
        final_df = commit_update(df_main, new_unique)
        print(f"[INFO] Total data akhir: {len(final_df)} baris.")
        print(f"[INFO] Quota remaining: {json.load(open(os.path.join(ROOT, 'data', 'raw', 'quota.json')) if os.path.exists(os.path.join(ROOT, 'data', 'raw', 'quota.json')) else open(os.path.join(ROOT, 'data', 'raw', 'quota.json'), 'w')) if False else 'tersimpan'}")
    else:
        final_df = df_new
        print('[INFO] Mode preview: data tidak di-commit ke CSV utama.')

    print('[OK] Proses fetch selesai.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('\n[INFO] Fetch dibatalkan oleh pengguna.')
        sys.exit(0)
