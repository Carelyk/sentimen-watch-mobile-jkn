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
| Data | **Mobile JKN** (ulasan Google Play, `app.bpjs.mobile`) |
| Dashboard | **Looker Studio** (data via Google Sheets) |
| Kanal alert | **GitHub Issue** (utama, otomatis); Discord webhook (opsional) |
| Penjadwal | GitHub Actions (cron harian) |
| Klasifikasi | Lexicon lokal (gratis, hemat limit); bisa ditingkatkan ke SVM/TF-IDF |
| LLM narasi | Gemini (utama) -> Groq (fallback), hanya saat ada anomali |
| SQL | DuckDB / SQLite untuk latihan query tren |
| Bahasa | Python 3.12 |

## Arsitektur singkat

```
GitHub Actions (cron harian)
  -> ambil ulasan terbaru         (google-play-scraper)     [pipeline/fetch_reviews.py]
  -> klasifikasi lokal            (lexicon + negasi)        [pipeline/classify.py]   <-- tanpa LLM
  -> deteksi anomali              (rasio vs baseline)       [pipeline/detect.py]
       |- normal  -> simpan, selesai                       (0 panggilan LLM)
       |- anomali -> 1x LLM narasi (Gemini -> Groq)         [pipeline/llm.py]
                     -> GitHub Issue (alert + arsip)        [pipeline/export.py]
                     -> Google Sheets -> Looker Studio      [pipeline/export.py]
                     -> Discord webhook (opsional)          [pipeline/export.py]
```

## Prinsip desain
1. Angka dihitung di server. LLM hanya **menarasikan**, bukan menentukan.
2. Dilarang mengarang angka; hanya angka yang di-inject yang boleh dipakai.
3. Output **JSON** supaya hasil bisa langsung dipakai sistem (dashboard/alert).
4. Prompt disimpan sebagai file -> ada riwayat perubahan (versionable).
5. LLM hanya dipanggil saat anomali -> hemat kuota gratis Gemini/Groq.

## Struktur folder
```
pipeline/            <- kode pipeline (jalankan sebagai modul)
  config.py             konfigurasi & ambang (baca .env)
  fetch_reviews.py      ambil ulasan Play Store
  classify.py           klasifikasi sentimen lokal (lexicon/negasi)
  detect.py             deteksi anomali vs baseline
  llm.py                panggil Gemini -> Groq, pakai template persona
  export.py             simpan JSON/CSV + Discord + Google Sheets (opsional)
  run.py                orkestrator harian
prompts/             <- template persona LLM
  data_analyst.md       insight harian
  data_scientist.md     evaluasi model (berkala)
  data_engineer.md      cek kualitas data (opsional)
data/
  sample_reviews.json   contoh data untuk uji tanpa internet
  sentiment_daily.csv   deret waktu harian (sumber dashboard)
  daily/                ringkasan JSON per hari
.github/workflows/   <- penjadwal harian (GitHub Actions)
```

## Cara menjalankan (lokal)
```powershell
cd C:\Users\User\Downloads\Project\Langflow
pip install -r requirements.txt

# Uji cepat tanpa internet & tanpa LLM:
python -m pipeline.run --offline --no-llm

# Jalankan normal (ambil ulasan asli):
python -m pipeline.run
```
Salin `.env.example` menjadi `.env` lalu isi kunci bila ingin narasi LLM,
notifikasi Discord, atau ekspor Google Sheets.

## Berapa banyak data yang diambil?
Default `REVIEW_COUNT=200`: **200 ulasan terbaru** setiap kali dijalankan
(jendela bergulir), diurutkan dari yang paling baru. Ubah lewat `.env` atau
env Actions, mis. `REVIEW_COUNT=500`. Makin besar -> tren makin halus,
tapi proses makin lama. Play Store Mobile JKN punya >1 juta ulasan, jadi
selalu ada data baru.

## Cara pakai di Langflow
1. Node **Prompt Template** -> isi salah satu file di `prompts/`.
2. Ganti variabel `{...}` dengan data dari pipeline (angka dihitung di server).
3. Untuk narasi harian pakai `data_analyst.md`; `data_scientist.md` untuk
   laporan kualitas model; `data_engineer.md` sebagai rambu sebelum diproses.

## Variabel tiap template
- `data_analyst.md`   : `{sumber_data}` `{periode}` `{baseline_hari}` `{audiens}` `{ringkasan_json}`
- `data_scientist.md` : `{dataset}` `{sampel}` `{metrik_json}` `{contoh_salah}`
- `data_engineer.md`  : `{sumber_data}` `{periode}` `{statistik_ingest}`

## Rahasia yang dibutuhkan (GitHub Secrets)
| Nama | Kegunaan | Wajib? |
| --- | --- | --- |
| `GEMINI_API_KEY` | narasi harian (utama) | disarankan |
| `GROQ_API_KEY` | narasi cadangan | opsional |
| `GITHUB_TOKEN` | buat Issue alert (otomatis di Actions) | tidak perlu diisi |
| `DISCORD_WEBHOOK_URL` | alert instan (opsional) | opsional |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | tulis ke Sheets | opsional |
| `GOOGLE_SHEET_ID` | ID spreadsheet Looker | opsional |

## Langkah berikutnya
- Ekspor CSV harian ke Google Sheets (service account) agar Looker Studio hidup.
- Notebook EDA + query SQL (DuckDB) di atas `data/sentiment_daily.csv`.
- Latih ulang SVM/TF-IDF dari notebook skripsi lalu sambungkan ke `classify.py`.
