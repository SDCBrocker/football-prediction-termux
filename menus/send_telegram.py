#!/usr/bin/env python3
"""Menu update database manual.

Fungsi utama:
- update dari file lokal
- update dari URL manual
- update dari input manual (paste CSV)
- update dari API
- preview data baru
- rollback backup terakhir
- history backup
"""

import os
import sys
import json
import shutil
from datetime import datetime
import pandas as pd
from tabulate import tabulate
from colorama import Fore, init

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_DB_PATH = os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv')
BACKUP_DIR = os.path.join(ROOT, 'data', 'backup')

init(autoreset=True)


def load_main_db(path=MAIN_DB_PATH):
    """Baca database utama."""
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def validate_new_data(df_new):
    """Validasi format data baru."""
    required = ['match_id', 'league', 'date', 'team', 'opponent']
    missing = [col for col in required if col not in df_new.columns]
    if missing:
        raise ValueError(f'Kolom wajib tidak ada: {missing}')
    if df_new['match_id'].duplicated().any():
        raise ValueError('Duplikat match_id ditemukan pada data baru.')
    return True


def preview_data(df_new, limit=10):
    """Tampilkan preview data baru."""
    print(tabulate(df_new.head(limit).fillna(''), headers='keys', tablefmt='grid'))


def deduplicate(df_main, df_new):
    """Hilangkan match_id yang sudah ada di main DB."""
    if df_main.empty:
        return df_new
    existing = set(df_main['match_id'].astype(str))
    return df_new[~df_new['match_id'].astype(str).isin(existing)].copy()


def backup_database():
    """Buat backup file main DB dengan timestamp."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target = os.path.join(BACKUP_DIR, f'matches_{stamp}.csv')
    if os.path.exists(MAIN_DB_PATH):
        shutil.copy2(MAIN_DB_PATH, target)
    return target


def commit_update(df_main, new_only):
    """Gabungkan data baru ke main DB."""
    df_combined = pd.concat([df_main, new_only], ignore_index=True)
    df_combined = df_combined.sort_values('date').reset_index(drop=True)
    os.makedirs(os.path.dirname(MAIN_DB_PATH), exist_ok=True)
    df_combined.to_csv(MAIN_DB_PATH, index=False)
    return df_combined


def rollback():
    """Rollback ke backup terakhir."""
    backups = sorted([os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith('.csv')])
    if not backups:
        print(Fore.YELLOW + '[INFO] Tidak ada backup.')
        return
    latest = backups[-1]
    choice = input(f'Rollback ke {latest}? (y/n): ').strip().lower()
    if choice == 'y':
        shutil.copy2(latest, MAIN_DB_PATH)
        print(f'[OK] Rollback selesai ke: {latest}')


def show_backup_history():
    """Tampilkan daftar backup."""
    backups = sorted([name for name in os.listdir(BACKUP_DIR) if name.endswith('.csv')]) if os.path.exists(BACKUP_DIR) else []
    if not backups:
        print(Fore.YELLOW + '[INFO] Belum ada backup.')
        return
    print(tabulate([[b] for b in backups], headers=['Backup'], tablefmt='grid'))


def main():
    """Loop menu update database."""
    while True:
        print(Fore.CYAN + '================================================')
        print(Fore.CYAN + '💾 UPDATE DATABASE')
        print(Fore.CYAN + '================================================')
        menu = [
            ['1', 'Update dari file lokal (data/raw/new_matches.csv)'],
            ['2', 'Update dari URL (input manual)'],
            ['3', 'Update dari input manual (paste CSV)'],
            ['4', 'Update dari API (fetch liga & musim)'],
            ['5', 'Lihat preview data baru'],
            ['6', 'Rollback ke backup terakhir'],
            ['7', 'Lihat history backup'],
            ['8', 'Kembali'],
        ]
        print(tabulate(menu, tablefmt='simple'))
        print(Fore.CYAN + '================================================')
        choice = input(Fore.YELLOW + 'Pilih menu [1-8]: ').strip()

        if choice == '1':
            source = os.path.join(ROOT, 'data', 'raw', 'new_matches.csv')
            if not os.path.exists(source):
                print(Fore.YELLOW + '[INFO] File baru belum ada: ' + source)
            else:
                df_new = pd.read_csv(source)
                validate_new_data(df_new)
                preview_data(df_new, limit=10)
                df_main = load_main_db()
                dedup = deduplicate(df_main, df_new)
                backup = backup_database()
                print(f'⚠️  Akan menambahkan {len(dedup)} laga baru.')
                print(f'Backup: {backup}')
                confirm = input('Lanjutkan? (y/n): ').strip().lower()
                if confirm == 'y':
                    commit_update(df_main, dedup)
                    print('[OK] Database berhasil diupdate.')
        elif choice == '2':
            print('[INFO] Fitur URL manual belum diimplementasi sepenuhnya. Masukkan URL CSV secara manual.')
        elif choice == '3':
            print('[INFO] Paste CSV ke terminal (ctrl+d untuk akhir input).')
            raw = sys.stdin.read()
            try:
                df_new = pd.read_csv(pd.io.common.StringIO(raw))
                validate_new_data(df_new)
                preview_data(df_new, 10)
                df_main = load_main_db()
                dedup = deduplicate(df_main, df_new)
                backup = backup_database()
                print(f'⚠️  Akan menambahkan {len(dedup)} laga baru.')
                print(f'Backup: {backup}')
                confirm = input('Lanjutkan? (y/n): ').strip().lower()
                if confirm == 'y':
                    commit_update(df_main, dedup)
                    print('[OK] Database berhasil diupdate.')
            except Exception as exc:
                print(f'[ERR] {exc}')
        elif choice == '4':
            print('[INFO] Fitur update dari API perlu dipanggil via scripts/fetch_api.py')
        elif choice == '5':
            path = os.path.join(ROOT, 'data', 'raw', 'new_matches.csv')
            if os.path.exists(path):
                preview_data(pd.read_csv(path), 10)
            else:
                print(Fore.YELLOW + '[INFO] Tidak ada data preview.')
        elif choice == '6':
            rollback()
        elif choice == '7':
            show_backup_history()
        elif choice == '8':
            break
        else:
            print(Fore.RED + 'Pilihan tidak valid.')

        input(Fore.WHITE + '\nTekan Enter untuk lanjut...')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[INFO] Update database dibatalkan oleh pengguna.')
