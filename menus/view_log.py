#!/usr/bin/env python3
"""Health check sistem prediksi parlay.

Fungsi utama:
- cek file penting
- cek disk space
- cek umur model
- cek error log
- tampilkan status dengan tabel
"""

import os
import subprocess
from datetime import datetime
import pandas as pd
import joblib
from tabulate import tabulate
from colorama import Fore, init

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

init(autoreset=True)


def check_files():
    """Cek file utama tersedia."""
    files = {
        '.env': os.path.join(ROOT, '.env'),
        'matches_normalized.csv': os.path.join(ROOT, 'data', 'processed', 'matches_normalized.csv'),
        'model_1x2.pkl': os.path.join(ROOT, 'models', 'model_1x2.pkl'),
        'model_ou.pkl': os.path.join(ROOT, 'models', 'model_ou.pkl'),
        'model_btts.pkl': os.path.join(ROOT, 'models', 'model_btts.pkl'),
    }
    status = {}
    for name, path in files.items():
        status[name] = '✓' if os.path.exists(path) else '✗'
    return status


def check_disk_space():
    """Cek disk space dengan df -h."""
    result = subprocess.run(['df', '-h'], capture_output=True, text=True)
    output = result.stdout.strip().splitlines()
    return output


def check_model_age():
    """Cek umur model, warning jika lebih dari 90 hari."""
    age_status = {}
    for name in ['model_1x2.pkl', 'model_ou.pkl', 'model_btts.pkl']:
        path = os.path.join(ROOT, 'models', name)
        if not os.path.exists(path):
            age_status[name] = '✗'
            continue
        delta_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))).days
        age_status[name] = '⚠' if delta_days > 90 else '✓'
    return age_status


def check_last_errors():
    """Cari kata error pada file log."""
    logs_dir = os.path.join(ROOT, 'logs')
    if not os.path.exists(logs_dir):
        return '✗'
    files = [os.path.join(logs_dir, name) for name in os.listdir(logs_dir) if name.endswith('.log')]
    if not files:
        return '⚠'
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read().lower()
                if 'error' in content:
                    return '⚠'
        except Exception:
            continue
    return '✓'


def print_status():
    """Tampilkan status health check dalam tabel."""
    file_status = check_files()
    age_status = check_model_age()
    disk_info = check_disk_space()
    print('=== HEALTH CHECK ===')
    rows = []
    for key, value in file_status.items():
        rows.append([key, value])
    rows.append(['Model Age', ' | '.join(f'{k}:{v}' for k, v in age_status.items())])
    rows.append(['Last Error', check_last_errors()])
    print(tabulate(rows, headers=['Item', 'Status'], tablefmt='grid'))
    print('\nDisk Usage:')
    for line in disk_info[:5]:
        print(line)
    return True


def main():
    """Entry point health check."""
    try:
        print_status()
        return 0
    except Exception as exc:
        print(f'[ERR] {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
