"""Backfill ulasan historis untuk membangun deret waktu dashboard.

Sekali jalan: tarik ulasan Play Store sampai mencakup ``--start``,
klasifikasi sentimen, lalu simpan:
  - data/backfill/raw_reviews.jsonl.gz   (mentah ter-gzip, TIDAK di-commit)
  - data/backfill/monthly.csv            (agregat bulanan, di-commit)
  - data/sentiment_daily.csv             (agregat harian, digabung, di-commit)

Aman diulang: baris tanggal yang sama akan diperbarui (idempotent).

Contoh:
    python -m pipeline.backfill --start 2025-01-01
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import classify, config, fetch_reviews

BACKFILL_DIR = config.DATA_DIR / "backfill"
BACKFILL_DIR.mkdir(parents=True, exist_ok=True)
LABELS = ("positif", "negatif", "netral")


def _parse_at(value) -> datetime:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _ratios(counts: dict, total: int) -> dict:
    return {
        "total": total,
        "positif": counts["positif"],
        "negatif": counts["negatif"],
        "netral": counts["netral"],
        "pos_ratio": round(counts["positif"] / total, 4) if total else 0.0,
        "neg_ratio": round(counts["negatif"] / total, 4) if total else 0.0,
    }


def fetch_since(start: datetime, max_count: int) -> list[dict]:
    items = fetch_reviews.fetch_reviews(count=max_count, save=False)
    kept: list[dict] = []
    for it in items:
        when = _parse_at(it["at"])
        if when >= start:
            row = dict(it)
            row["_at"] = when
            kept.append(row)
    return kept


def aggregate(labeled: list[dict]) -> tuple[dict, dict]:
    daily: dict[str, dict] = defaultdict(lambda: {k: 0 for k in LABELS})
    monthly: dict[str, dict] = defaultdict(lambda: {k: 0 for k in LABELS})
    for it in labeled:
        when: datetime = it["_at"]
        daily[when.strftime("%Y-%m-%d")][it["sentimen"]] += 1
        monthly[when.strftime("%Y-%m")][it["sentimen"]] += 1
    return daily, monthly


def write_raw(labeled: list[dict]) -> Path:
    path = BACKFILL_DIR / "raw_reviews.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for it in labeled:
            fh.write(
                json.dumps(
                    {
                        "review_id": it.get("review_id"),
                        "at": it["_at"].isoformat(),
                        "score": it.get("score"),
                        "version": it.get("version"),
                        "thumbs_up": it.get("thumbs_up"),
                        "content": it.get("content"),
                        "sentimen": it.get("sentimen"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def merge_daily(daily: dict) -> Path:
    """Gabungkan agregat harian ke data/sentiment_daily.csv tanpa menghapus baris lain."""
    from . import export

    rows: dict[str, dict] = {}
    if config.CSV_PATH.exists():
        rows = {r["date"]: r for r in export._read_csv_rows()}

    for day, counts in daily.items():
        total = sum(counts.values())
        r = _ratios(counts, total)
        prev = rows.get(day, {})
        rows[day] = {
            "date": day,
            "total": total,
            "positif": r["positif"],
            "negatif": r["negatif"],
            "netral": r["netral"],
            "pos_ratio": r["pos_ratio"],
            "neg_ratio": r["neg_ratio"],
            "anomaly": prev.get("anomaly", "0"),
            "llm_provider": prev.get("llm_provider", ""),
        }

    with config.CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=export.CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows[k] for k in sorted(rows))
    return config.CSV_PATH


def write_monthly(monthly: dict) -> Path:
    path = BACKFILL_DIR / "monthly.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["bulan", "total", "positif", "negatif", "netral", "pos_ratio", "neg_ratio"]
        )
        for month in sorted(monthly):
            counts = monthly[month]
            total = sum(counts.values())
            r = _ratios(counts, total)
            writer.writerow(
                [
                    month, total, r["positif"], r["negatif"], r["netral"],
                    r["pos_ratio"], r["neg_ratio"],
                ]
            )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill ulasan historis")
    parser.add_argument("--start", default="2025-01-01", help="tanggal awal (YYYY-MM-DD)")
    parser.add_argument("--max", type=int, default=120000, help="maksimum ulasan ditarik")
    args = parser.parse_args(argv)

    start = _parse_at(args.start)
    print(f"[backfill] menarik sampai {args.max} ulasan (target >= {args.start}) ...")
    items = fetch_since(start, args.max)
    print(f"[backfill] ulasan dalam rentang: {len(items)}")
    if items:
        dates = [it["_at"] for it in items]
        print(f"[backfill] rentang: {min(dates)} .. {max(dates)}")

    labeled = classify.classify_reviews(items)
    daily, monthly = aggregate(labeled)
    raw = write_raw(labeled)
    dpath = merge_daily(daily)
    mpath = write_monthly(monthly)
    print(f"[backfill] mentah  : {raw}")
    print(f"[backfill] bulanan : {mpath}")
    print(f"[backfill] harian  : {dpath} ({len(daily)} hari)")

    print("[backfill] ringkas bulanan:")
    for month in sorted(monthly):
        counts = monthly[month]
        total = sum(counts.values())
        print(
            f"  {month}: {total:>7} ulasan | "
            f"negatif {counts['negatif'] / total * 100:5.1f}% | "
            f"positif {counts['positif'] / total * 100:5.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
