#!/usr/bin/env python3
"""Penyiapan folder kerja untuk proyek Termux.

File ini memastikan struktur data, model, log, dan cache sudah tersedia
sebelum semua modul dipanggil.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

folders = [
    ROOT / 'data' / 'raw' / 'cache',
    ROOT / 'data' / 'processed',
    ROOT / 'data' / 'backup',
    ROOT / 'logs',
    ROOT / 'models',
]

for folder in folders:
    folder.mkdir(parents=True, exist_ok=True)

for marker in [
    ROOT / 'data' / 'raw' / 'cache' / '.gitkeep',
    ROOT / 'data' / 'processed' / '.gitkeep',
    ROOT / 'data' / 'backup' / '.gitkeep',
    ROOT / 'logs' / '.gitkeep',
    ROOT / 'models' / '.gitkeep',
]:
    if not marker.exists():
        marker.write_text('', encoding='utf-8')

print('Folder project siap dibuat.')
