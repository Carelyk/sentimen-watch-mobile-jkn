# Sentimen Watch — Catatan Proyek

Portofolio **Data Analyst** dengan otomasi sebagai pembeda:
pipeline otomatis -> analisis -> dashboard + alert, hemat limit LLM.

Cerita satu kalimat:
> "Saya bikin sistem yang tiap hari membaca data baru, menandai lonjakan,
> lalu mengirim insight otomatis — dan saya desain supaya LLM hanya
> dipanggil saat benar-benar perlu."

---

## Keputusan sejauh ini

| Aspek | Pilihan |
| --- | --- |
| Positioning | Data Analyst (+ otomasi sebagai pembeda) |
| Data | **Mobile JKN** — ulasan Google Play (`app.bpjs.mobile`), **2025–2026 (97.566 ulasan)** |
| Dashboard | **Looker Studio** (data via Google Sheets) |
| Kanal alert | **GitHub Issue** (utama, otomatis); Discord webhook (opsional) |
| Penjadwal | GitHub Actions (cron harian) |
| Klasifikasi | Lexicon lokal (gratis, hemat limit); bisa ditingkatkan ke SVM/TF-IDF |
| LLM narasi | **Groq (utama) -> Gemini (fallback)** — model `openai/gpt-oss-120b`, hanya saat ada anomali |
| SQL | DuckDB / SQLite untuk latihan query tren |
| Bahasa | Python 3.12 |

## Arsitektur singkat

```
GitHub Actions (cron harian)
  -> ambil ulasan terbaru         (google-play-scraper)     [pipeline/fetch_reviews.py]
  -> klasifikasi lokal            (lexicon + negasi)        [pipeline/classify.py]   <-- tanpa LLM
  -> deteksi anomali              (rasio vs baseline)       [pipeline/detect.py]
       |- normal  -> simpan, selesai                       (0 panggilan LLM)
       |- anomali -> 1x LLM narasi (Groq -> Gemini)         [pipeline/llm.py]
                     -> GitHub Issue (alert + arsip)        [pipeline/export.py]
                     -> Google Sheets -> Looker Studio      [pipeline/export.py]
                     -> Discord webhook (opsional)          [pipeline/export.py]
```

## Prinsip desain
1. Angka dihitung di server. LLM hanya **menarasikan**, bukan menentukan.
2. Dilarang mengarang angka; hanya angka yang di-inject yang boleh dipakai.
3. Output **JSON** supaya hasil bisa langsung dipakai sistem (dashboard/alert).
4. Prompt disimpan sebagai file -> ada riwayat perubahan (versionable).
5. LLM hanya dipanggil saat anomali -> hemat kuota gratis Groq/Gemini.

## Struktur folder
```
pipeline/            <- kode pipeline (jalankan sebagai modul)
  config.py             konfigurasi & ambang (baca .env)
  fetch_reviews.py      ambil ulasan Play Store
  classify.py           klasifikasi sentimen lokal (lexicon/negasi)
  detect.py             deteksi anomali vs baseline
  llm.py                panggil Groq -> Gemini, pakai template persona
  export.py             simpan JSON/CSV + GitHub Issue + Discord + Sheets
  backfill.py           tarik riwayat 2025 -> sekarang (sekali jalan)
  push_sheets.py        kirim seluruh riwayat ke Google Sheets
  run.py                orkestrator harian
prompts/             <- template persona LLM
  data_analyst.md       insight harian (untuk manajemen)
  data_scientist.md     evaluasi model (berkala)
  data_engineer.md      cek kualitas data (opsional)
  warga.md              ringkasan bahasa awam untuk publik
notebooks/
  01_eda.ipynb          EDA + query SQL (DuckDB) + grafik
docs/
  looker_studio.md      panduan dashboard Looker Studio (gratis)
data/
  sample_reviews.json   contoh data untuk uji tanpa internet
  sentiment_daily.csv   deret waktu harian 2025-2026 (sumber dashboard)
  backfill/monthly.csv  agregat bulanan (sumber dashboard)
  daily/                ringkasan JSON per hari
.github/workflows/   <- penjadwal harian (GitHub Actions)
requirements.txt       dependensi pipeline
requirements-eda.txt   dependensi notebook EDA
```

## Cara menjalankan (lokal)
```powershell
cd C:\Users\User\Downloads\Project\Langflow
pip install -r requirements.txt

# Uji cepat tanpa internet & tanpa LLM:
python -m pipeline.run --offline --no-llm

# Jalankan normal (ambil ulasan asli):
python -m pipeline.run

# Backfill riwayat 2025 -> sekarang (sekali saja, aman diulang):
python -m pipeline.backfill --start 2025-01-01
```
Salin `.env.example` menjadi `.env` lalu isi kunci bila ingin narasi LLM,
notifikasi Discord, atau ekspor Google Sheets.

> Catatan Windows: pakai virtualenv milik proyek -> `.venv\Scripts\python -m pipeline.run`

## Data historis (backfill 2025–2026)
Play Store menaruh ulasan terbaru di depan, jadi `pipeline/backfill.py` menarik
sampai **120.000 ulasan** lalu menyaring tanggal >= `--start`. Hasil nyata saat ini:

- **97.566 ulasan** dari **1 Jan 2025 – sekarang**, mencakup **647 hari**.
- `data/backfill/monthly.csv` — agregat bulanan (di-commit, untuk dashboard).
- `data/sentiment_daily.csv` — agregat harian yang digabung (di-commit, 647 baris).
- `data/backfill/raw_reviews.jsonl.gz` — mentah (~5,7 MB, **tidak** di-commit).

Ringkas bulanan memperlihatkan pola musiman, mis. rasio negatif memuncak pada
**Feb 2025 (30,6%)** dan **Sep 2026 (30,3%)**, sementara sentimen positif
tertinggi pada **Des 2025 (54,3%)** — bahan cerita yang bagus.

## Berapa banyak data yang diambil?
Default `REVIEW_COUNT=200`: **200 ulasan terbaru** setiap kali dijalankan
(jendela bergulir), diurutkan dari yang paling baru. Ubah lewat `.env` atau
env Actions, mis. `REVIEW_COUNT=500`. Makin besar -> tren makin halus,
tapi proses makin lama. Play Store Mobile JKN punya >1 juta ulasan, jadi
selalu ada data baru.

## Analisis (notebook) & dashboard
- **EDA + SQL**: buka `notebooks/01_eda.ipynb` — tren harian, pola bulanan, dan
  beberapa query DuckDB. Pasang dulu: `pip install -r requirements-eda.txt`.
- **Dashboard gratis**: panduan lengkap di `docs/looker_studio.md`
  (Google Sheets -> Looker Studio). Isi seluruh riwayat sekali jalan:
  ```powershell
  .\.venv\Scripts\python -m pipeline.push_sheets
  ```

## Cara pakai di Langflow
1. Node **Prompt Template** -> isi salah satu file di `prompts/`.
2. Ganti variabel `{...}` dengan data dari pipeline (angka dihitung di server).
3. `data_analyst.md` untuk narasi manajemen; `warga.md` untuk versi bahasa awam;
   `data_scientist.md` untuk laporan kualitas model; `data_engineer.md` sebagai
   rambu sebelum diproses.

## Variabel tiap template
- `data_analyst.md`   : `{sumber_data}` `{periode}` `{baseline_hari}` `{audiens}` `{ringkasan_json}`
- `warga.md`          : `{sumber_data}` `{periode}` `{ringkasan_json}`
- `data_scientist.md` : `{dataset}` `{sampel}` `{metrik_json}` `{contoh_salah}`
- `data_engineer.md`  : `{sumber_data}` `{periode}` `{statistik_ingest}`

## Flow Langflow — "Sentimen Watch — Mobile JKN"

Selain pipeline Python di atas, repo ini punya **flow visual Langflow** untuk demo
analisis cepat satu berkas ulasan (import lalu jalankan).

### Rantai node
```
Read File (upload)
  -> Prompt Template 1  {text}
  -> Language Model      (gemini-3.8-flash)
  -> Load JSON           (JSON string)
       |- Parser  "{summary}"     -> Prompt Template 2 {summary, sentiment}
       |- Parser  "{sentiment}"   ->            |
                                                 v
                              Language Model 2 (gemini-3.8-flash) -> Chat Output
```

### Kenapa begini (catatan teknis)
- **Tipe harus nyambung.** `Load JSON` mengeluarkan tipe `JSON`, sedangkan variabel di
  `Prompt Template` menerima `Message`. Perantara **`Parser`** (input JSON/Data →
  output `Message`) yang menjembatani. Menyambung `JSON → Prompt` langsung ditolak
  Langflow ("invalid handles").
- **`Parser` → Mode = Parser, output `Parsed Text`.** Field **Mode** dan output tetap
  dipertahankan; pola `{summary}` dan `{sentiment}` memecah JSON hasil LLM.
- **Tanpa `jq`.** Komponen `Load JSON` memakai `json_repair` (sudah terpasang), jadi
  tidak perlu `pip install jq` seperti komponen "Parse JSON".
- **Model `gemini-3.8-flash`.** `gemini-2.5-flash` sudah deprecated (404 NOT_FOUND);
  Google menyarankan `gemini-3.8-flash`.
- **File harus di-upload, bukan path lokal.** Karena
  `LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS=true`, `Read File` menolak path lokal. Upload
  CSV ke storage flow → nilai `path` menjadi `<flow_id>/<timestamp>_<nama_file>`.

### Data yang dipakai
`data/ulasan_mobile_jkn_sample.csv` — **1.000 ulasan** Mobile JKN dari Google Play
(`app.bpjs.mobile`), kolom `content, score, at, appVersion`, rentang **30 Sep – 9 Okt 2026**
(distribusi rating: 594×bintang 5, 296×bintang 1, sisanya bintang 2–4).
File contoh kecil lain: `data/langflow_contoh_ulasan.csv` (40 baris, format
`review,rating,source`) dan `data/langflow_contoh_ulasan_bjps.csv` (40 baris, format
sama seperti sample).

### Cara import & jalankan
1. Di Langflow: **Import** flow → pilih JSON flow ini.
2. Buka node **Read File** → **upload** `data/ulasan_mobile_jkn_sample.csv`.
3. Pastikan kredensial **Google AI** (`GOOGLE_API_KEY`) tersedia di Langflow.
4. **Run** → keluaran JSON: `{ summary, sentiment, action_item[], catatan_keterbatasan }`.

## Rahasia yang dibutuhkan (GitHub Secrets)
| Nama | Kegunaan | Wajib? |
| --- | --- | --- |
| `GROQ_API_KEY` | narasi harian (utama) | disarankan |
| `GEMINI_API_KEY` | narasi cadangan | opsional |
| `GITHUB_TOKEN` | buat Issue alert (otomatis di Actions) | tidak perlu diisi |
| `DISCORD_WEBHOOK_URL` | alert instan (opsional) | opsional |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | tulis ke Sheets | opsional |
| `GOOGLE_SHEET_ID` | ID spreadsheet Looker | opsional |

## Langkah berikutnya
- Analisis kata kunci dari `data/backfill/raw_reviews.jsonl.gz`.
- Latih ulang SVM/TF-IDF dari notebook skripsi lalu sambungkan ke `classify.py`.
- Tambah chart Looker Studio (time series + musiman) mengikuti `docs/looker_studio.md`.
