# Checklist Sistem Prediksi Parlay (Termux)

Berikut checklist 13 fase yang harus dipenuhi sebelum sistem dianggap siap.

## 1. Setup environment [ ] status ⬜
- [ ] Python 3 tersedia
- [ ] requirements.txt terinstall
- [ ] .env dibuat dari .env.example
- [ ] folder data/logs/models dibuat

## 2. Konfigurasi API [ ] status ⬜
- [ ] API_KEY valid
- [ ] API_BASE_URL benar
- [ ] LEAGUES sesuai target
- [ ] SEASONS sesuai target

## 3. Fetch data [ ] status ⬜
- [ ] fixture berhasil diambil
- [ ] stats berhasil diambil
- [ ] standings berhasil diambil
- [ ] odds berhasil diambil
- [ ] cache 24 jam aktif

## 4. Validasi data [ ] status ⬜
- [ ] kolom wajib lengkap
- [ ] tidak ada duplikat match_id
- [ ] quota API tercatat

## 5. Clean data [ ] status ⬜
- [ ] drop leakage column
- [ ] missing value ditangani
- [ ] tanggal dikonversi

## 6. Feature engineering [ ] status ⬜
- [ ] differential raw dibuat
- [ ] rolling features dengan shift(1)
- [ ] home/away features dibuat
- [ ] H2H features dibuat

## 7. Normalisasi [ ] status ⬜
- [ ] league coefficient diterapkan
- [ ] z-score per liga dibuat
- [ ] kolom adjusted sesuai aturan

## 8. Training model [ ] status ⬜
- [ ] split time-based 80/20
- [ ] 3 model terlatih
- [ ] hasil evaluasi disimpan
- [ ] akurasi >80% dicek untuk leakage

## 9. Backtest [ ] status ⬜
- [ ] model test terbaca
- [ ] akurasi per confidence dihitung
- [ ] value betting diterapkan
- [ ] bankroll simulation dibuat

## 10. Prediksi hari ini [ ] status ⬜
- [ ] fixtures_today.csv ada
- [ ] model dipanggil
- [ ] prediction JSON dibuat
- [ ] kalau value rendah, difilter

## 11. Update database [ ] status ⬜
- [ ] backup dibuat
- [ ] deduplikasi berjalan
- [ ] update manual/URL/API aman

## 12. Telegram & monitoring [ ] status ⬜
- [ ] token valid
- [ ] chat id aktif
- [ ] log aktif
- [ ] health check ditampilkan

## 13. Final check [ ] status ⬜
- [ ] semua fase ✅
- [ ] sistem siap produksi
- [ ] dokumentasi dibaca ulang

Catatan final:
Jika pada fase mana pun ditemukan leakage, data tidak valid, atau akurasi tidak masuk akal, ulangi dari fase terkait sebelum produksi.
