"""Ambil ulasan dari Google Play Store memakai google-play-scraper.

Modul ini sengaja menyimpan data seperlunya saja (tanpa nama pengguna) demi privasi.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


def _snapshot_path(stamp: str) -> Path:
    return config.RAW_DIR / f"reviews_{stamp}.json"


def fetch_reviews(offline: bool = False) -> list[dict]:
    """Kembalikan daftar ulasan terbaru (maksimum ``config.REVIEW_COUNT``).

    Setiap item: review_id, score, version, at, content, thumbs_up.
    Dengan ``offline=True`` dipakai data/sample_reviews.json (untuk uji tanpa internet).
    """
    if offline:
        return load_offline()

    try:
        from google_play_scraper import Sort, reviews
    except ImportError as exc:  # pragma: no cover - bergantung lingkungan
        raise SystemExit(
            "google-play-scraper belum terpasang.\n"
            "Jalankan: pip install -r requirements.txt"
        ) from exc

    result, _ = reviews(
        config.APP_ID,
        lang=config.REVIEW_LANG,
        country=config.REVIEW_COUNTRY,
        sort=Sort.NEWEST,
        count=config.REVIEW_COUNT,
    )

    items: list[dict] = []
    for r in result:
        items.append(
            {
                "review_id": r.get("reviewId"),
                "score": int(r.get("score") or 0),
                "version": r.get("reviewCreatedVersion") or "",
                "at": (r.get("at") or datetime.now(timezone.utc)).isoformat(),
                "content": (r.get("content") or "").strip(),
                "thumbs_up": int(r.get("thumbsUpCount") or 0),
            }
        )

    stamp = datetime.now().strftime("%Y-%m-%d")
    _snapshot_path(stamp).write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return items


def load_offline() -> list[dict]:
    sample = config.DATA_DIR / "sample_reviews.json"
    if not sample.exists():
        raise SystemExit(
            "Mode offline butuh data/sample_reviews.json (belum ada)."
        )
    return json.loads(sample.read_text(encoding="utf-8"))
