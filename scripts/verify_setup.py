#!/usr/bin/env python3
"""Menu untuk melihat log terbaru.

Fitur:
- pilih file log
- tampilkan 50 baris terakhir
- search keyword
- warna berdasarkan level log
"""

import os
import subprocess
from colorama import Fore, Style, init

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(ROOT, 'logs')

init(autoreset=True)


def list_logs():
    """List semua file log di folder logs."""
    if not os.path.exists(LOG_DIR):
        return []
    return sorted([name for name in os.listdir(LOG_DIR) if name.endswith('.log')])


def read_log(path, limit=50, keyword=None):
    """Baca log terakhir dan tampilkan dengan warna."""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()[-limit:]
    except FileNotFoundError:
        print(Fore.RED + '[ERR] File log tidak ditemukan.')
        return

    for line in lines:
        lowered = line.lower()
        if keyword and keyword.lower() not in lowered:
            continue
        if 'error' in lowered:
            color = Fore.RED
        elif 'warning' in lowered:
            color = Fore.YELLOW
        else:
            color = Fore.WHITE
        print(color + line.rstrip())


def main():
    """Loop menu log."""
    while True:
        print('================================================')
        print('📊 LIHAT LOG')
        print('================================================')
        logs = list_logs()
        if not logs:
            print('[INFO] Tidak ada log yang tersedia.')
            return
        for i, name in enumerate(logs, 1):
            print(f'{i}. {name}')
        print(f'{len(logs)+1}. Kembali')
        selection = input('Pilih log [1-' + str(len(logs)+1) + ']: ').strip()
        if selection == str(len(logs)+1):
            return
        try:
            chosen = logs[int(selection)-1]
            keyword = input('Filter keyword (kosongkan = semua): ').strip()
            read_log(os.path.join(LOG_DIR, chosen), keyword=keyword or None)
        except Exception as exc:
            print(Fore.RED + f'[ERR] {exc}')
        input('\nTekan Enter untuk lanjut...')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[INFO] Lihat log dibatalkan.')
