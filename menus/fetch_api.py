#!/usr/bin/env python3
"""Menu interaktif untuk fetch data dari API.

Opsi:
1. Fetch 1 Liga-Musim
2. Fetch Semua Liga-Musim
3. Preview Data
4. Cek Quota
5. Clear Cache
6. Lihat Estimasi Request
7. Update ke Database Utama
8. Kembali
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd
from colorama import Fore, Style, init

init(autoreset=True)

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Load konfigurasi dari .env."""
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    return {
        'API_KEY': os.getenv('API_KEY', ''),
        'LEAGUES': os.getenv('LEAGUES', 'EPL').split(','),
        'SEASONS': os.getenv('SEASONS', '2024').split(','),
    }


def deduplicate(df_old, df_new):
    """Hapus baris dari df_new yang sudah ada di df_old."""
    if df_old.empty:
        return df_new
    if df_new.empty:
        return df_new

    key_cols = [col for col in ['match_id', 'team', 'is_home'] if col in df_old.columns and col in df_new.columns]
    if not key_cols:
        return df_new

    df_new_only = df_new[
        ~df_new[key_cols].apply(tuple, axis=1).isin(
            df_old[key_cols].apply(tuple, axis=1)
        )
    ].copy()
    return df_new_only


def preview_df(df, limit=5):
    """Tampilkan preview DataFrame dengan warna."""
    if df.empty:
        print(Fore.YELLOW + "[INFO] DataFrame kosong.")
        return
    print(Fore.CYAN + f"\n{df.head(limit).to_string()}")
    print(Fore.CYAN + f"\n[INFO] Total rows: {len(df)} | Columns: {len(df.columns)}")


def save_result(df, label='matches_raw'):
    """Simpan DataFrame ke CSV dengan backup + deduplikasi."""
    output_path = os.path.join(ROOT, 'data', 'processed', f'{label}.csv')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if df is None or df.empty:
        print(Fore.YELLOW + '[INFO] Data kosong, tidak disimpan.')
        return

    if os.path.exists(output_path):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(ROOT, 'data', 'backup')
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f'{label}_{stamp}.csv')
        with open(output_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        print(Fore.GREEN + f'[OK] Backup: {backup_path}')

        df_old = pd.read_csv(output_path)
        df_new = deduplicate(df_old, df)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
        if 'date' in df_final.columns:
            df_final['date'] = pd.to_datetime(df_final['date'], errors='coerce')
            df_final = df_final.sort_values('date').reset_index(drop=True)
        df_final.to_csv(output_path, index=False)
        print(Fore.GREEN + f'[OK] Merge: {len(df_new)} baris baru, total {len(df_final)}')
    else:
        df.to_csv(output_path, index=False)
        print(Fore.GREEN + f'[OK] Disimpan ke {output_path}')


def check_quota():
    """Cek quota API: coba fetch dari API, fallback ke file lokal."""
    try:
        from scripts.fetch_api import fetch_api
        data = fetch_api('/quota', {})
        remaining = data.get('remaining', 'unknown') if isinstance(data, dict) else 'unknown'
        print(Fore.CYAN + f"[API] Quota remaining: {remaining}")
        return
    except Exception as exc:
        print(Fore.YELLOW + f"[WARN] Gagal fetch quota dari API: {exc}")

    quota_path = os.path.join(ROOT, 'data', 'raw', 'quota.json')
    if not os.path.exists(quota_path):
        print(Fore.YELLOW + '[INFO] Belum ada data quota lokal.')
        return

    try:
        with open(quota_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        print(Fore.CYAN + f"[FILE] Quota remaining: {data.get('remaining', 'unknown')}")
        print(f"Terakhir diperbarui: {data.get('timestamp', '-')}")
    except (json.JSONDecodeError, IOError) as exc:
        print(Fore.RED + f"[ERROR] Gagal baca quota.json: {exc}")


def clear_cache_menu():
    """Menu untuk clear cache API."""
    cache_dir = ROOT / "data" / "raw" / "cache"
    if not cache_dir.exists():
        print(Fore.YELLOW + "[INFO] Cache kosong.")
        return

    files = list(cache_dir.glob("*.json"))
    print(Fore.YELLOW + f"[INFO] Total cache files: {len(files)}")

    confirm = input(Fore.YELLOW + "Hapus semua cache? (y/n): ").strip().lower()
    if confirm != 'y':
        return

    for file in files:
        try:
            file.unlink()
        except OSError as exc:
            print(Fore.RED + f"[ERROR] Gagal hapus {file}: {exc}")
    print(Fore.GREEN + f"[OK] {len(files)} cache files dihapus.")


def fetch_all_menu():
    """Menu untuk fetch semua liga-musim dengan estimasi quota."""
    env = load_env()
    leagues = env.get('LEAGUES', ['EPL'])
    seasons = env.get('SEASONS', ['2024'])
    total = len(leagues) * len(seasons)

    print(Fore.CYAN + f'[INFO] Liga: {len(leagues)}, Musim: {len(seasons)}')
    print(Fore.CYAN + f'[INFO] Total kombinasi: {total}')

    estimated = total * 2 + total * 380 * 2
    print(Fore.YELLOW + f'[WARN] Estimasi request: ~{estimated}')
    print(Fore.YELLOW + f'[WARN] Free tier OpenFootAPI: 5.000 req/bulan')

    if estimated > 4000:
        print(Fore.RED + '[WARN] Estimasi melebihi quota free tier!')
        print(Fore.RED + '[WARN] Kurangi liga/musim, atau upgrade API key.')

    confirm = input(Fore.YELLOW + 'Lanjutkan fetch all? (y/n): ').strip().lower()
    if confirm != 'y':
        print('[INFO] Dibatalkan.')
        return pd.DataFrame()

    script_path = ROOT / "scripts" / "fetch_api.py"
    try:
        subprocess.run([sys.executable, str(script_path)], cwd=str(ROOT), check=False)
    except Exception as exc:
        print(Fore.RED + f"[ERROR] {exc}")


def update_main_db_menu():
    """Update ke database utama matches_normalized.csv."""
    raw_path = os.path.join(ROOT, 'data', 'processed', 'matches_raw.csv')
    main_path = os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv')

    if not os.path.exists(raw_path):
        print(Fore.RED + '[ERROR] matches_raw.csv tidak ada. Fetch dulu.')
        return

    df_new = pd.read_csv(raw_path)
    if df_new.empty:
        print(Fore.YELLOW + '[INFO] Data kosong.')
        return

    print(Fore.CYAN + f'\n[INFO] Akan menambahkan {len(df_new)} baris')
    preview_df(df_new, 5)

    confirm = input(Fore.YELLOW + 'Lanjutkan? (y/n): ').strip().lower()
    if confirm != 'y':
        print('[INFO] Dibatalkan.')
        return

    if os.path.exists(main_path):
        df_main = pd.read_csv(main_path)
    else:
        df_main = pd.DataFrame()

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(ROOT, 'data', 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(main_path):
        backup_path = os.path.join(backup_dir, f'matches_normalized_{stamp}.csv')
        with open(main_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        print(Fore.GREEN + f'[OK] Backup: {backup_path}')

    df_new_only = deduplicate(df_main, df_new)
    df_final = pd.concat([df_main, df_new_only], ignore_index=True)
    if 'date' in df_final.columns:
        df_final['date'] = pd.to_datetime(df_final['date'], errors='coerce')
        df_final = df_final.sort_values('date').reset_index(drop=True)
    df_final.to_csv(main_path, index=False)
    print(Fore.GREEN + f'[OK] Database utama: {len(df_new_only)} baris baru, total {len(df_final)}')


def main():
    """Loop menu fetch API."""
    menu_items = [
        ['1', 'Fetch 1 Liga-Musim'],
        ['2', 'Fetch Semua Liga-Musim'],
        ['3', 'Preview Data'],
        ['4', 'Cek Quota'],
        ['5', 'Clear Cache'],
        ['6', 'Lihat Estimasi Request'],
        ['7', 'Update ke Database Utama'],
        ['8', 'Kembali'],
    ]

    while True:
        print("\n" + Fore.CYAN + "=" * 50)
        print(Fore.CYAN + "FETCH API")
        print(Fore.CYAN + "=" * 50)
        for num, label in menu_items:
            print(f"{Fore.CYAN}{num}{Style.RESET_ALL}. {label}")

        try:
            choice = input(Fore.YELLOW + 'Pilih menu [1-8]: ').strip()
        except EOFError:
            print(Fore.YELLOW + '\n[INFO] Input terminal berakhir. Keluar.')
            break

        if choice == '1':
            print("[INFO] Menu fetch 1 liga-musim belum diimplementasikan.")
        elif choice == '2':
            fetch_all_menu()
        elif choice == '3':
            raw_path = ROOT / "data" / "processed" / "matches_raw.csv"
            if raw_path.exists():
                df = pd.read_csv(raw_path)
                preview_df(df, 10)
            else:
                print(Fore.YELLOW + "[INFO] Data belum ada.")
        elif choice == '4':
            check_quota()
        elif choice == '5':
            clear_cache_menu()
        elif choice == '6':
            env = load_env()
            leagues = env.get('LEAGUES', ['EPL'])
            seasons = env.get('SEASONS', ['2024'])
            print(Fore.CYAN + f'[INFO] Estimasi: {len(leagues) * len(seasons) * 2} requests')
        elif choice == '7':
            update_main_db_menu()
        elif choice == '8':
            break
        else:
            print(Fore.RED + "[ERROR] Pilihan tidak valid.")

        try:
            input(Fore.WHITE + '\nTekan Enter untuk lanjut...')
        except EOFError:
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[INFO] Menu fetch_api dibatalkan.")
