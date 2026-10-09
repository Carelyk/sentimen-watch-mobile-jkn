"""Orkestrator pipeline harian Sentimen Watch.

Contoh pakai:
    python -m pipeline.run                 # jalankan normal (butuh internet)
    python -m pipeline.run --offline       # pakai data contoh, tanpa internet
    python -m pipeline.run --no-llm        # hitung saja, tanpa panggil LLM
    python -m pipeline.run --force-llm     # paksa buat narasi walau tidak anomali
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

from . import classify, config, detect, export, fetch_reviews, llm


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline harian Sentimen Watch")
    parser.add_argument("--offline", action="store_true", help="pakai data/sample_reviews.json")
    parser.add_argument("--no-llm", action="store_true", help="lewati pemanggilan LLM")
    parser.add_argument("--force-llm", action="store_true", help="paksa buat narasi LLM")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    date_str = datetime.now().strftime("%Y-%m-%d")

    try:
        items = fetch_reviews.fetch_reviews(offline=args.offline)
    except SystemExit as exc:
        print(exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Gagal mengambil ulasan: {exc}")
        return 1

    labeled = classify.classify_reviews(items)
    summary = detect.summarize(labeled)
    baseline = detect.load_baseline()
    verdict = detect.evaluate(summary, baseline)

    print("=" * 56)
    print(f"Sentimen Watch - {config.APP_NAME}")
    print(f"Tanggal  : {date_str}")
    print(f"Total    : {summary['total']} ulasan")
    print(f"Positif  : {summary['positif']} ({summary['pos_ratio'] * 100:.1f}%)")
    print(f"Negatif  : {summary['negatif']} ({summary['neg_ratio'] * 100:.1f}%)")
    print(f"Netral   : {summary['netral']}")
    base = baseline.get("neg_ratio")
    print(f"Baseline : {base if base is not None else 'belum ada'} "
          f"({baseline.get('days', 0)} hari)")
    print(f"Anomali  : {verdict['anomaly']} {verdict.get('reasons', [])}")
    print("=" * 56)

    insight = None
    provider = None
    if (verdict["anomaly"] or args.force_llm) and not args.no_llm:
        prompt = llm.build_prompt(date_str, summary, baseline, verdict)
        result = llm.call_llm(prompt)
        provider = result.get("provider")
        insight = llm.parse_json(result.get("text"))
        if insight is None:
            print("[LLM] tidak tersedia/gagal:", result.get("errors"))
            if result.get("text"):
                print("[LLM mentah]", str(result["text"])[:500])
        else:
            print(f"[LLM:{provider}]", json.dumps(insight, ensure_ascii=False)[:900])
    elif not verdict["anomaly"]:
        print("[LLM] dilewati (tidak ada anomali) — hemat limit.")
    else:
        print("[LLM] dilewati (--no-llm).")

    export.save_daily(
        date_str,
        {
            "date": date_str,
            "app": config.APP_NAME,
            "summary": summary,
            "baseline": baseline,
            "verdict": verdict,
            "provider": provider,
            "insight": insight,
        },
    )
    export.upsert_csv(date_str, summary, verdict["anomaly"], provider)
    if verdict["anomaly"]:
        issue_url = export.notify_github_issue(date_str, summary, verdict, insight)
        if issue_url:
            print("[GitHub] issue dibuat:", issue_url)
        sent = export.notify_discord(date_str, summary, verdict, insight)
        if sent:
            print("[Discord] notifikasi terkirim.")
    if export.push_sheets(date_str, summary, verdict["anomaly"], provider):
        print("[Sheets] baris tersimpan.")

    print("Selesai. Hasil:", config.DAILY_DIR / f"{date_str}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
