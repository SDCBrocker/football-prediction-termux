#!/usr/bin/env bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

mkdir -p data/raw/cache data/processed data/backup logs

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[INFO] File .env dibuat dari .env.example. Silakan edit nilai API dan Telegram."
fi

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

chmod +x scripts/*.py menus/*.py 2>/dev/null || true

echo "[OK] Setup selesai. Jalankan: bash main_menu.sh"
