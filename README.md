# Sistem Prediksi Parlay (Termux)

Sistem prediksi parlay berbasis machine learning untuk liga sepakbola dengan fokus pada O/U fleksibel (1.5, 2.5, 3.5), dan data API OpenFootAPI. Proyek ini dibuat untuk dijalankan di Termux, dengan menu interaktif dan pipeline data dari fetch hingga prediksi.

Quick Start:
1. Buka Termux
2. Jalankan: bash setup.sh
3. Edit file .env sesuai kunci API dan Telegram
4. Jalankan: bash main_menu.sh

Struktur folder:
- scripts/: pipeline data, fitur, training, backtest, prediksi
- menus/: menu interaktif untuk operasi harian
- data/raw/: data mentah dan cache API
- data/processed/: data hasil pembersihan, feature engineering, normalisasi
- data/backup/: backup database sebelum update
- models/: model hasil training
- logs/: file log aktivitas
- docs/: catatan seperti README dan checklist

Menu interaktif:
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

Peringatan penting:
- Jangan skip fase pipeline.
- Cek CHECKLIST.md sebelum produksi.
- Jika akurasi >80% curiga leakage, lalu retrain segera.
- Retrain model setiap 3 bulan jika data baru terus berkembang.
- Gunakan validasi time-based, bukan random split.

Troubleshooting:
| Masalah | Solusi |
| --- | --- |
| Token API salah | Periksa .env dan API_KEY |
| Rate limit API | Tunggu dan gunakan cache 24 jam |
| File CSV kosong | Cek fetch atau hasil API |
| Model tidak ada | Jalankan script train.py |
| Telegram gagal kirim | Cek TOKEN dan CHAT_ID |
| Error pandas/numpy | Pastikan requirements.txt sudah terinstall |

