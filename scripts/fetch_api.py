#!/usr/bin/env python3
"""Menu utama aplikasi prediksi parlay untuk Termux.

Menu interaktif dengan tabulate & colorama. Script dipanggil via subprocess,
setiap kali kembali ke menu layar dibersihkan.
"""

import os
import sys
import subprocess
import time
from tabulate import tabulate
from colorama import Fore, Back, Style, init

init(autoreset=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def clear_screen():
    """Bersihkan layar sesuai platform."""
    os.system('clear' if os.name != 'nt' else 'cls')


def run_script(script_path, *args):
    """Jalankan script Python lain via subprocess."""
    command = [sys.executable, script_path, *args]
    try:
        result = subprocess.run(command, cwd=ROOT)
        return result.returncode
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[INFO] Proses dibatalkan oleh pengguna.")
        time.sleep(1)
        return 0


def show_menu():
    """Tampilkan menu utama."""
    menu = [
        ["1", "📡 Fetch Data dari API"],
        ["2", "🧹 Clean Data"],
        ["3", "🛠️  Feature Engineering"],
        ["4", "📊 Normalisasi"],
        ["5", "🤖 Training Model"],
        ["6", "🧪 Backtest"],
        ["7", "🔮 Prediksi Hari Ini"],
        ["8", "📋 Cek Result"],
        ["9", "💾 Update Database"],
        ["10", "📤 Kirim ke Telegram"],
        ["11", "🏥 Health Check"],
        ["12", "📊 Lihat Log"],
        ["13", "❌ Keluar"],
    ]
    print(Fore.CYAN + "=" * 60)
    print(Fore.CYAN + "SISTEM PREDIKSI PARLAY - TERMUX")
    print(Fore.CYAN + "=" * 60)
    print(tabulate(menu, tablefmt='simple'))
    print(Fore.CYAN + "=" * 60)


def main():
    """Loop menu utama."""
    while True:
        try:
            clear_screen()
            show_menu()
            choice = input(Fore.YELLOW + "Pilih menu [1-13]: ").strip()

            if choice == '1':
                run_script(os.path.join(ROOT, 'menus', 'fetch_api.py'))
            elif choice == '2':
                run_script(os.path.join(ROOT, 'scripts', 'clean_data.py'))
            elif choice == '3':
                run_script(os.path.join(ROOT, 'scripts', 'features.py'))
            elif choice == '4':
                run_script(os.path.join(ROOT, 'scripts', 'normalize.py'))
            elif choice == '5':
                run_script(os.path.join(ROOT, 'scripts', 'train.py'))
            elif choice == '6':
                run_script(os.path.join(ROOT, 'scripts', 'backtest.py'))
            elif choice == '7':
                run_script(os.path.join(ROOT, 'scripts', 'predict.py'))
            elif choice == '8':
                run_script(os.path.join(ROOT, 'menus', 'check_result.py'))
            elif choice == '9':
                run_script(os.path.join(ROOT, 'menus', 'update_database.py'))
            elif choice == '10':
                run_script(os.path.join(ROOT, 'menus', 'send_telegram.py'))
            elif choice == '11':
                run_script(os.path.join(ROOT, 'menus', 'healthcheck.py'))
            elif choice == '12':
                run_script(os.path.join(ROOT, 'menus', 'view_log.py'))
            elif choice == '13':
                print(Fore.GREEN + "Terima kasih. Sistem ditutup.")
                break
            else:
                print(Fore.RED + "Pilihan tidak valid. Silakan pilih 1-13.")
                time.sleep(1)

            input(Fore.WHITE + "\nTekan Enter untuk kembali ke menu...")

        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n[INFO] Ctrl+C terdeteksi. Keluar dari menu utama.")
            break


if __name__ == '__main__':
    main()
