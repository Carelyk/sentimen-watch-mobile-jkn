# Dashboard Looker Studio (gratis) via Google Sheets

Alur: **pipeline → Google Sheets → Looker Studio**. Semua gratis.

- Sheet `harian`  : dari `data/sentiment_daily.csv` (647 hari, terus bertambah)
- Sheet `bulanan` : dari `data/backfill/monthly.csv` (agregat per bulan)

---

## Bagian A — Siapkan Service Account (sekali saja)

1. Buka <https://console.cloud.google.com> → **New Project** (mis. `sentimen-watch`).
2. **APIs & Services → Library**, aktifkan dua hal:
   - **Google Sheets API**
   - **Google Drive API**
3. **APIs & Services → Credentials → Create credentials → Service account**
   - Nama: `sentimen-watch`. Klik **Create and continue**, lalu **Done**.
4. Klik service account itu → tab **Keys** → **Add key → Create new key → JSON**.
   File JSON akan terunduh. **Simpan baik-baik** (ini rahasia).
   - Catat email service account: `...@....iam.gserviceaccount.com`.
5. Buat spreadsheet baru di <https://sheets.new> dan beri nama,
   mis. `Sentimen Watch - Mobile JKN`.
6. **Share** spreadsheet itu ke email service account di langkah 4, dengan
   akses **Editor**. (Kalau tidak di-share, penulisan akan gagal.)
7. Ambil **ID spreadsheet** dari URL:
   `https://docs.google.com/spreadsheets/d/`**`<ID_PANJANG>`**`/edit`

## Bagian B — Konfigurasi & isi awal (lokal)

Isi `.env`:
```
GOOGLE_SERVICE_ACCOUNT_JSON=C:\path\ke\key.json
GOOGLE_SHEET_ID=<ID_PANJANG>
```

Pindahkan seluruh riwayat 2025–2026 ke sheet:
```powershell
.\.venv\Scripts\python -m pipeline.push_sheets
```
Hasilnya: tab `harian` (647 baris) dan `bulanan` (22 baris).

## Bagian C — Otomatisasi harian (GitHub Actions)

Agar setiap hari ikut terisi, buka repo → **Settings → Secrets and variables →
Actions → New repository secret**, tambahkan:

| Nama | Isi |
| --- | --- |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | **tempel seluruh isi** file JSON (bukan path-nya) |
| `GOOGLE_SHEET_ID` | ID spreadsheet |

Workflow `daily.yml` sudah otomatis menambah baris baru tiap hari.

## Bagian D — Bangun laporan di Looker Studio

1. Buka <https://lookerstudio.google.com> → **Create → Report**.
2. **Add data → Google Sheets** → pilih spreadsheet & tab **harian** → **Add**.
3. Chart yang disarankan:
   - **Time series**: X = `date`, Y = `neg_ratio` + `pos_ratio`
     → langsung terlihat tren & lonjakan.
   - **Scorecard**: `total` (dengan filter "date = hari terakhir").
   - **Time series (bar)**: agregat bulanan (pakai tab `bulanan`) → musiman.
   - **Table**: 10 hari dengan `neg_ratio` tertinggi.
4. (Opsional) Tambah kalkulasi field *moving average* 7 hari untuk meredam noise:
   `AVG(neg_ratio)` dengan *date range* 7 hari terakhir.

## Catatan
- Looker Studio menyegarkan data dari Sheets otomatis (sekitar 15 menit).
- Kuota gratis Google Sheets API jauh lebih dari cukup untuk 1 baris/hari.
- Jangan pernah commit file JSON service account ke Git — sudah masuk `.gitignore`.
