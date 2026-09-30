#!/usr/bin/env python3
"""Menu interaktif fetch data dari API untuk Termux.

Menu ini menyediakan akses cepat ke fetch fixtures, stats, odds, standings,
serta operasi gabungan yang dipakai dalam workflow data mining.
"""

import os
import sys
import json
import time
from dotenv import load_dotenv
from tabulate import tabulate
from colorama import Fore, Style, init
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.fetch_api import (
    fetch_fixtures,
    fetch_stats,
    fetch_standings,
    fetch_odds,
    build_match_rows,
    validate_data,
    deduplicate,
    backup_database,
    commit_update,
    load_env,
)

init(autoreset=True)


def clear_screen():
    """Bersihkan layar."""
    os.system('clear' if os.name != 'nt' else 'cls')


def preview_df(df, limit=10):
    """Tampilkan preview DataFrame dengan tabulate."""
    if df is None or df.empty:
        print(Fore.YELLOW + '[INFO] Data kosong.')
        return
    print(tabulate(df.head(limit).fillna(''), tablefmt='grid', headers='keys'))


def fetch_fixtures_menu():
    """Menu fetch fixtures 1 liga 1 musim."""
    print('\n=== FETCH FIXTURES ===')
    league = input('Masukkan liga (contoh: EPL): ').strip()
    season = input('Masukkan musim (contoh: 2024): ').strip()
    df = fetch_fixtures(league, season)
    preview_df(df, 10)
    return df


def fetch_stats_menu():
    """Menu fetch stats per match_id."""
    print('\n=== FETCH STATS ===')
    match_id = input('Masukkan match_id: ').strip()
    df = fetch_stats(match_id)
    preview_df(df, 10)
    return df


def fetch_standings_menu():
    """Menu fetch standings untuk liga & musim."""
    print('\n=== FETCH STANDINGS ===')
    league = input('Masukkan liga: ').strip()
    season = input('Masukkan musim: ').strip()
    df = fetch_standings(league, season)
    preview_df(df, 10)
    return df


def fetch_odds_menu():
    """Menu fetch odds per match_id."""
    print('\n=== FETCH ODDS ===')
    match_id = input('Masukkan match_id: ').strip()
    df = fetch_odds(match_id)
    preview_df(df, 10)
    return df


def fetch_all_menu():
    """Fetch semua liga dan musim dengan progress."""
    env = load_env()
    leagues = env.get('LEAGUES', ['EPL'])
    seasons = env.get('SEASONS', ['2024'])
    total = len(leagues) * len(seasons)
    print(f'[INFO] Estimasi request: {total * 3}')
    confirm = input('Lanjutkan fetch all? (y/n): ').strip().lower()
    if confirm != 'y':
        print('[INFO] Dibatalkan.')
        return pd.DataFrame()

    frames = []
    for idx, league in enumerate(leagues, 1):
        for season in seasons:
            print(f"\n[PROGRESS] {idx}/{total} -> {league} {season}")
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
            frames.append(build_match_rows(fixtures, stats, standings, odds))
            time.sleep(1)

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    preview_df(result, 10)
    return result


def fetch_combo_menu():
    """Fetch fixtures + stats + odds untuk satu liga."""
    print('\n=== FETCH COMBO ===')
    league = input('Masukkan liga: ').strip()
    season = input('Masukkan musim: ').strip()
    fixtures = fetch_fixtures(league, season)
    standings = fetch_standings(league, season)
    stats = pd.DataFrame()
    odds = pd.DataFrame()
    for match_id in fixtures['match_id'].dropna().astype(str).unique():
        stats_df = fetch_stats(match_id)
        odds_df = fetch_odds(match_id)
        if not stats_df.empty:
            stats = pd.concat([stats, stats_df], ignore_index=True)
        if not odds_df.empty:
            odds = pd.concat([odds, odds_df], ignore_index=True)
    df = build_match_rows(fixtures, stats, standings, odds)
    preview_df(df, 10)
    return df


def check_quota():
    """Cek quota API yang tersimpan di file quota.json."""
    quota_path = os.path.join(ROOT, 'data', 'raw', 'quota.json')
    if not os.path.exists(quota_path):
        print(Fore.YELLOW + '[INFO] Belum ada data quota. Fetch data terlebih dahulu.')
        return

    with open(quota_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    print(Fore.CYAN + f"Quota remaining: {data.get('remaining', 'unknown')}")
    print(f"Terakhir diperbarui: {data.get('timestamp', '-')}")


def save_result(df, label='matches_raw'):
    """Simpan DataFrame ke CSV main untuk data baru."""
    output_path = os.path.join(ROOT, 'data', 'processed', f'{label}.csv')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f'[OK] Disimpan ke {output_path}')


def main():
    """Loop menu interaktif fetch API."""
    while True:
        clear_screen()
        print(Fore.CYAN + '================================================')
        print(Fore.CYAN + '📡 FETCH DATA DARI API')
        print(Fore.CYAN + '================================================')
        menu = [
            ['1', 'Fetch Fixtures (1 liga, 1 musim)'],
            ['2', 'Fetch Stats (per match_id)'],
            ['3', 'Fetch Standings (1 liga, 1 musim)'],
            ['4', 'Fetch Odds (per match_id)'],
            ['5', 'Fetch All (10 liga, 3 musim)'],
            ['6', 'Fetch Fixtures + Stats + Odds (1 liga)'],
            ['7', 'Lihat Quota API'],
            ['8', 'Kembali'],
        ]
        print(tabulate(menu, tablefmt='simple'))
        print(Fore.CYAN + '================================================')

        choice = input(Fore.YELLOW + 'Pilih menu [1-8]: ').strip()

        if choice == '1':
            df = fetch_fixtures_menu()
            if not df.empty:
                save_result(df, 'matches_raw')
        elif choice == '2':
            fetch_stats_menu()
        elif choice == '3':
            fetch_standings_menu()
        elif choice == '4':
            fetch_odds_menu()
        elif choice == '5':
            df = fetch_all_menu()
            if not df.empty:
                save_result(df, 'matches_raw')
        elif choice == '6':
            df = fetch_combo_menu()
            if not df.empty:
                save_result(df, 'matches_raw')
        elif choice == '7':
            check_quota()
        elif choice == '8':
            break
        else:
            print(Fore.RED + 'Pilihan tidak valid.')

        input(Fore.WHITE + '\nTekan Enter untuk lanjut...')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[INFO] Proses fetch dibatalkan oleh pengguna.')
