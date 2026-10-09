"""Klasifikasi sentimen lokal: lexicon berbahasa Indonesia + penanganan negasi.

Ini baseline yang **gratis dan tanpa limit** (tidak memanggil LLM).
Kualitas bisa ditingkatkan dengan menukar fungsinya ke model SVM/TF-IDF
hasil notebook skripsi (lihat catatan di bagian bawah).
"""
from __future__ import annotations

import re

# --- Kamus sentimen (kata tunggal, huruf kecil) -----------------------------
POSITIVE: set[str] = {
    "bagus", "baik", "mantap", "keren", "hebat", "suka", "senang", "mudah",
    "cepat", "lancar", "membantu", "bermanfaat", "memuaskan", "puas", "nyaman",
    "jelas", "lengkap", "akurat", "praktis", "berguna", "berhasil", "aman",
    "terbaik", "sempurna", "ramah", "responsif", "stabil", "ringan", "murah",
    "gratis", "terpercaya", "andal", "canggih", "modern", "rapi", "bersih",
    "informatif", "solutif", "enak", "sukses", "membahagiakan", "terbantu",
    "memudahkan", "membaik", "meningkat", "peningkatan", "joss", "sip", "oke",
    "top", "lumayan", "direkomendasikan", "merekomendasikan", "alhamdulillah",
    "terimakasih", "good", "nice", "love", "helpful", "excellent", "kerennya",
}

NEGATIVE: set[str] = {
    "jelek", "buruk", "parah", "error", "eror", "gagal", "susah", "sulit",
    "lambat", "lemot", "lelet", "lag", "ngelag", "hang", "macet", "ribet",
    "rumit", "bingung", "membingungkan", "kecewa", "mengecewakan", "payah",
    "kacau", "rusak", "bug", "crash", "stuck", "lama", "lamban", "boros",
    "mahal", "berat", "menyebalkan", "menjengkelkan", "mengganggu", "gangguan",
    "masalah", "kendala", "keluhan", "komplain", "denda", "tagihan", "diblokir",
    "diblok", "ditolak", "dipersulit", "mempersulit", "gajelas", "spam",
    "iklan", "sampah", "busuk", "tolol", "bodoh", "brengsek", "menyusahkan",
    "menyulitkan", "kesal", "marah", "jengkel", "sedih", "takut", "khawatir",
    "waswas", "ragu", "minim", "sepi", "kotor", "buruknya", "parahnya",
    "keterlaluan", "menipu", "penipuan", "kosong", "hilang", "lambatnya",
    "muter", "hancur", "kacaukan",
}

NEGATION: set[str] = {
    "tidak", "bukan", "belum", "jangan", "tak", "tanpa", "kurang",
    "nggak", "gak", "ga", "gk", "enggak", "tiada",
}

NEGATION_WINDOW = 3

# Normalisasi singkatan/slang umum di ulasan Indonesia.
NORMALISASI: dict[str, str] = {
    "gak": "tidak", "ga": "tidak", "gk": "tidak", "nggak": "tidak",
    "ngga": "tidak", "enggak": "tidak", "tdk": "tidak", "gk": "tidak",
    "udah": "sudah", "udh": "sudah", "yg": "yang", "dgn": "dengan",
    "utk": "untuk", "dr": "dari", "krn": "karena", "bgt": "sangat",
    "banget": "sangat", "lemot": "lambat", "lelet": "lambat", "eror": "error",
    "app": "aplikasi", "apps": "aplikasi", "hp": "ponsel", "ribet": "rumit",
    "mantul": "mantap", "kelar": "selesai", "parah": "parah", "bintang1": "bintang",
}

_TOKEN_RE = re.compile(r"[a-z]+")


def _normalize(text: str) -> str:
    return text.lower()


def _tokens(text: str) -> list[str]:
    words = _TOKEN_RE.findall(_normalize(text))
    return [NORMALISASI.get(w, w) for w in words]


def classify_text(text: str) -> tuple[str, float]:
    """Kembalikan (label, skor_absolut). label: positif | negatif | netral."""
    words = _tokens(text or "")
    score = 0
    for i, w in enumerate(words):
        polarity = 0
        if w in POSITIVE:
            polarity = 1
        elif w in NEGATIVE:
            polarity = -1
        if polarity == 0:
            continue
        start = max(0, i - NEGATION_WINDOW)
        if any(neg in NEGATION for neg in words[start:i]):
            polarity = -polarity
        score += polarity

    if score > 0:
        label = "positif"
    elif score < 0:
        label = "negatif"
    else:
        label = "netral"
    return label, float(abs(score))


def classify_reviews(items: list[dict]) -> list[dict]:
    """Tambahkan field ``sentimen`` dan ``skor`` ke setiap ulasan."""
    labeled: list[dict] = []
    for it in items:
        label, score = classify_text(it.get("content", ""))
        row = dict(it)
        row["sentimen"] = label
        row["skor"] = score
        labeled.append(row)
    return labeled


# --- Opsi peningkatan: pakai model SVM/TF-IDF dari notebook skripsi ---------
# Simpan model ke models/svm.pkl dan models/tfidf.pkl, lalu ganti pemanggilan
# classify_reviews di run.py dengan versi model ini.
def load_svm_model(models_dir):
    try:
        import joblib
        from pathlib import Path

        base = Path(models_dir)
        model_p = base / "svm.pkl"
        vec_p = base / "tfidf.pkl"
        if model_p.exists() and vec_p.exists():
            return joblib.load(model_p), joblib.load(vec_p)
    except Exception:
        return None
    return None
