#!/usr/bin/env python3
"""Kirim rekomendasi parlay ke Telegram.

Fungsi:
- baca .env
- baca predictions_today.json
- format pesan markdown
- konfirmasi user
- kirim via requests.post ke Telegram Bot API
- log hasil ke logs/notify.log
"""

import os
import json
import time
from datetime import datetime
import requests
from dotenv import load_dotenv
from colorama import Fore, init

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREDICTIONS_PATH = os.path.join(ROOT, 'data', 'processed', 'predictions_today.json')
LOG_PATH = os.path.join(ROOT, 'logs', 'notify.log')

init(autoreset=True)


def load_env():
    """Baca konfigurasi token Telegram dari .env."""
    load_dotenv(os.path.join(ROOT, '.env'))
    token = os.getenv('TELEGRAM_TOKEN', '').strip()
    chat_id = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    return token, chat_id


def load_predictions(path=PREDICTIONS_PATH):
    """Baca data prediksi yang sudah dibuat."""
    if not os.path.exists(path):
        raise FileNotFoundError(f'File prediksi tidak ditemukan: {path}')
    with open(path, 'r', encoding='utf-8') as file:
        return json.load(file)


def format_message(predictions):
    """Format pesan dianggap sebagai parlay, termasuk leg per leg."""
    lines = ['🎯 *REKOMENDASI PARLAY*', '']
    for match in predictions[:3]:
        lines.append(f"*{match.get('home')} vs {match.get('away')}* ({match.get('league')})")
        for leg in match.get('predictions', []):
            lines.append(
                f"- {leg.get('market')}: {leg.get('prediction')} | odds={leg.get('odds')} | "
                f"prob={leg.get('confidence', 0):.2%} | value={leg.get('value', 0):.2%} | stake={0.01:.2f}"
            )
        lines.append('')
    return '\n'.join(lines)


def send_telegram(token, chat_id, message):
    """Kirim pesan ke Telegram."""
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown',
    }
    for attempt in range(3):
        try:
            response = requests.post(url, data=payload, timeout=30)
            if response.status_code in (200, 201):
                return True
            if response.status_code in (400, 401):
                raise ValueError(f'Telegram error: {response.text}')
            time.sleep(2)
        except Exception:
            if attempt == 2:
                raise
    return False


def log_message(message, status):
    """Catat hasil pengiriman Telegram ke logs/notify.log."""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as file:
        file.write(f"{datetime.now().isoformat()} | {status} | {message}\n")


def main():
    """Entry point kirim rekomendasi Telegram."""
    print('=== KIRIM KE TELEGRAM ===')
    token, chat_id = load_env()
    if not token or not chat_id:
        print('[ERR] TELEGRAM_TOKEN atau TELEGRAM_CHAT_ID belum diisi di .env')
        return 1

    predictions = load_predictions()
    message = format_message(predictions)
    print(message)
    confirm = input('Kirim message ke Telegram? (y/n): ').strip().lower()
    if confirm != 'y':
        print('[INFO] Pengiriman dibatalkan.')
        return 0

    try:
        result = send_telegram(token, chat_id, message)
        if result:
            print('[OK] Pesan berhasil dikirim ke Telegram.')
            log_message(message, 'success')
        else:
            print('[ERR] Gagal mengirim ke Telegram.')
            log_message(message, 'failed')
    except Exception as exc:
        print(f'[ERR] Error: {exc}')
        log_message(str(exc), 'error')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
