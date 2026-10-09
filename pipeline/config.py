"""Konfigurasi terpusat untuk pipeline Sentimen Watch.

Semua angka & kunci dibaca dari satu tempat (env / .env) supaya mudah diaudit.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv opsional
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DAILY_DIR = DATA_DIR / "daily"
STATE_DIR = DATA_DIR / "state"
PROMPTS_DIR = ROOT / "prompts"
CSV_PATH = DATA_DIR / "sentiment_daily.csv"

for _p in (RAW_DIR, DAILY_DIR, STATE_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# --- Aplikasi target ---
APP_ID = os.getenv("APP_ID", "app.bpjs.mobile")
APP_NAME = os.getenv("APP_NAME", "Mobile JKN")
REVIEW_COUNTRY = os.getenv("REVIEW_COUNTRY", "id")
REVIEW_LANG = os.getenv("REVIEW_LANG", "id")
REVIEW_COUNT = int(os.getenv("REVIEW_COUNT", "200"))

# --- Ambang deteksi anomali ---
BASELINE_DAYS = int(os.getenv("BASELINE_DAYS", "7"))
MIN_REVIEWS = int(os.getenv("MIN_REVIEWS", "20"))
NEG_RATIO_ALERT = float(os.getenv("NEG_RATIO_ALERT", "0.35"))
NEG_RATIO_INCREASE = float(os.getenv("NEG_RATIO_INCREASE", "0.5"))

# --- LLM narasi ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Provider pertama yang dicoba: "groq" (default, hemat kuota Gemini) atau "gemini".
LLM_PRIMARY = os.getenv("LLM_PRIMARY", "groq").strip().lower()

# --- Notifikasi & dashboard ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()

# --- GitHub Issue (kanal alert berbasis repo; otomatis terisi di Actions) ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "").strip()  # format "owner/repo"
