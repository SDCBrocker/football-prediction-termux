#!/usr/bin/env python3
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pathlib import Path

BASE = Path(__file__).resolve().parent

# Membuat struktur folder penting
for folder in [
    BASE / 'data' / 'raw' / 'cache',
    BASE / 'data' / 'processed',
    BASE / 'data' / 'backup',
    BASE / 'logs',
    BASE / 'models',
]:
    folder.mkdir(parents=True, exist_ok=True)

# File .gitkeep agar folder terekam di Git
for path in [
    BASE / 'data' / 'raw' / 'cache' / '.gitkeep',
    BASE / 'data' / 'processed' / '.gitkeep',
    BASE / 'data' / 'backup' / '.gitkeep',
    BASE / 'logs' / '.gitkeep',
    BASE / 'models' / '.gitkeep',
]:
    if not path.exists():
        path.write_text('', encoding='utf-8')

print('Struktur folder berhasil dibuat.')
