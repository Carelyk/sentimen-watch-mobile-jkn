"""Deteksi anomali: bandingkan rasio negatif hari ini terhadap baseline.

Baseline dihitung dari ``BASELINE_DAYS`` baris terakhir pada CSV harian.
Logikanya sengaja sederhana dan transparan supaya mudah dipertanggungjawabkan.
"""
from __future__ import annotations

import csv
from typing import Any

from . import config

LABELS = ("positif", "negatif", "netral")


def summarize(items: list[dict]) -> dict[str, Any]:
    total = len(items)
    counts = {label: 0 for label in LABELS}
    for it in items:
        label = it.get("sentimen", "netral")
        counts[label] = counts.get(label, 0) + 1
    neg_ratio = counts["negatif"] / total if total else 0.0
    pos_ratio = counts["positif"] / total if total else 0.0
    return {
        "total": total,
        "positif": counts["positif"],
        "negatif": counts["negatif"],
        "netral": counts["netral"],
        "pos_ratio": round(pos_ratio, 4),
        "neg_ratio": round(neg_ratio, 4),
    }


def load_baseline() -> dict[str, Any]:
    """Rata-rata rasio negatif dari N hari terakhir yang tersimpan di CSV."""
    if not config.CSV_PATH.exists():
        return {"days": 0, "neg_ratio": None}

    with config.CSV_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    ratios: list[float] = []
    for row in rows:
        value = row.get("neg_ratio")
        if value not in (None, ""):
            try:
                ratios.append(float(value))
            except ValueError:
                continue

    recent = ratios[-config.BASELINE_DAYS:]
    if not recent:
        return {"days": 0, "neg_ratio": None}
    return {"days": len(recent), "neg_ratio": round(sum(recent) / len(recent), 4)}


def evaluate(summary: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Tentukan apakah hari ini dianggap anomali."""
    if summary["total"] < config.MIN_REVIEWS:
        return {
            "anomaly": False,
            "reasons": [
                f"data kurang ({summary['total']} < {config.MIN_REVIEWS}); belum cukup untuk menilai"
            ],
        }

    reasons: list[str] = []
    base = baseline.get("neg_ratio")
    if base:
        threshold = base * (1 + config.NEG_RATIO_INCREASE)
        if summary["neg_ratio"] >= threshold:
            reasons.append(
                f"rasio negatif naik >= {config.NEG_RATIO_INCREASE * 100:.0f}% "
                f"vs baseline ({(summary['neg_ratio'] - base) * 100:+.1f} poin)"
            )
    if summary["neg_ratio"] >= config.NEG_RATIO_ALERT:
        reasons.append(
            f"rasio negatif >= {config.NEG_RATIO_ALERT * 100:.0f}% "
            f"({summary['neg_ratio'] * 100:.1f}%)"
        )

    return {"anomaly": bool(reasons), "reasons": reasons}
