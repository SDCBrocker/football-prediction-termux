#!/usr/bin/env python3
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Buat folder penting
for folder in [
    ROOT / 'data' / 'raw' / 'cache',
    ROOT / 'data' / 'processed',
    ROOT / 'data' / 'backup',
    ROOT / 'logs',
    ROOT / 'models',
]:
    folder.mkdir(parents=True, exist_ok=True)

print('Folder siap.')
