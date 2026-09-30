#!/usr/bin/env python3
"""Menu utama Sistem Prediksi Parlay untuk Termux.

Menu ini menjalankan setiap tahap pipeline melalui subprocess agar setiap
modul berjalan sebagai proses terpisah dan error dapat terlihat jelas.

Menu:
1. Fetch Data dari API
2. Clean Data
3. Feature Engineering
4. Normalisasi
5. Training Model
6. Backtest
7. Prediksi Hari Ini
8. Cek Result
9. Update Database
10. Kirim ke Telegram
11. Health Check
12. Lihat Log
13. Keluar
"""

import os
import sys
import subprocess
import time
from pathlib import Path

from colorama import Fore, Style, init
from tabulate import tabulate

init(autoreset=True)

ROOT = Path(__file__).resolve().parent.parent

MENU_ITEMS = [
    ("1", "📡 Fetch Data dari API", ROOT / "menus" / "fetch_api.py"),
    ("2", "🧹 Clean Data", ROOT / "scripts" / "clean_data.py"),
    ("3", "🛠️  Feature Engineering", ROOT / "scripts" / "features.py"),
    ("4", "📊 Normalisasi", ROOT / "scripts" / "normalize.py"),
    ("5", "🤖 Training Model", ROOT / "scripts" / "train.py"),
    ("6", "🧪 Backtest", ROOT / "scripts" / "backtest.py"),
    ("7", "🔮 Prediksi Hari Ini", ROOT / "scripts" / "predict.py"),
    ("8", "📋 Cek Result", ROOT / "menus" / "check_result.py"),
    ("9", "💾 Update Database", ROOT / "menus" / "update_database.py"),
    ("10", "📤 Kirim ke Telegram", ROOT / "menus" / "send_telegram.py"),
    ("11", "🏥 Health Check", ROOT / "menus" / "healthcheck.py"),
    ("12", "📊 Lihat Log", ROOT / "menus" / "view_log.py"),
    ("13", "❌ Keluar", None),
]


def clear_screen():
    """Membersihkan terminal setiap kali menu ditampilkan kembali."""
    os.system("cls" if os.name == "nt" else "clear")


def ensure_directories():
    """Membuat folder kerja yang dibutuhkan sebelum menu dijalankan."""
    for relative_path in (
        "data/raw",
        "data/raw/cache",
        "data/processed",
        "data/backup",
        "logs",
        "models",
        "notebooks",
        "scripts",
        "menus",
    ):
        (ROOT / relative_path).mkdir(parents=True, exist_ok=True)


def show_menu():
    """Menampilkan daftar pilihan utama."""
    print(Fore.CYAN + "=" * 64)
    print(Fore.CYAN + "SISTEM PREDIKSI PARLAY - TERMUX")
    print(Fore.CYAN + "=" * 64)
    print(tabulate([[number, label] for number, label, _ in MENU_ITEMS],
                   headers=["No", "Menu"], tablefmt="simple"))
    print(Fore.CYAN + "=" * 64)


def run_script(script_path):
    """Menjalankan modul Python dengan interpreter yang sedang digunakan."""
    if not script_path.exists():
        print(Fore.RED + f"[ERROR] File tidak ditemukan: {script_path}")
        return 1

    print(Fore.YELLOW + f"\n[INFO] Menjalankan: {script_path.relative_to(ROOT)}\n")
    try:
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(ROOT),
            check=False,
        )
        if completed.returncode == 0:
            print(Fore.GREEN + "\n[OK] Proses selesai tanpa status error.")
        else:
            print(Fore.RED + f"\n[ERROR] Proses berhenti dengan exit code {completed.returncode}.")
        return completed.returncode
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[INFO] Proses dibatalkan dengan Ctrl+C.")
        return 130
    except OSError as exc:
        print(Fore.RED + f"\n[ERROR] Gagal menjalankan subprocess: {exc}")
        return 1


def pause():
    """Menunggu pengguna sebelum menu ditampilkan kembali."""
    try:
        input(Fore.WHITE + "\nTekan Enter untuk kembali ke menu utama...")
    except EOFError:
        time.sleep(1)


def main():
    """Loop menu utama sampai pengguna memilih opsi 13 (Keluar)."""
    ensure_directories()

    while True:
        try:
            clear_screen()
            show_menu()
            choice = input(Fore.YELLOW + "Pilih menu [1-13]: ").strip()
            selected = next((item for item in MENU_ITEMS if item[0] == choice), None)

            if selected is None:
                print(Fore.RED + "Pilihan tidak valid. Masukkan angka 1 sampai 13.")
                time.sleep(1)
                continue

            _, label, script_path = selected
            if script_path is None:
                print(Fore.GREEN + "Sistem ditutup. Sampai jumpa.")
                return 0

            run_script(script_path)
            pause()

        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n[INFO] Ctrl+C terdeteksi. Keluar dari menu utama.")
            return 0
        except EOFError:
            print(Fore.YELLOW + "\n[INFO] Input terminal berakhir. Keluar.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
