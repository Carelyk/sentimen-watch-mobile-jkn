"""Simpan hasil harian (JSON + CSV) dan kirim notifikasi/ekspor opsional."""
from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from typing import Any

from . import config

CSV_FIELDS = [
    "date", "total", "positif", "negatif", "netral",
    "pos_ratio", "neg_ratio", "anomaly", "llm_provider",
]


def save_daily(date_str: str, payload: dict[str, Any]) -> str:
    path = config.DAILY_DIR / f"{date_str}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _read_csv_rows() -> list[dict]:
    if not config.CSV_PATH.exists():
        return []
    with config.CSV_PATH.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def upsert_csv(date_str: str, summary: dict, anomaly: bool, provider: str | None) -> None:
    """Tulis satu baris per tanggal (mengganti baris tanggal yang sama bila ada)."""
    rows = [r for r in _read_csv_rows() if r.get("date") != date_str]
    rows.append(
        {
            "date": date_str,
            "total": summary["total"],
            "positif": summary["positif"],
            "negatif": summary["negatif"],
            "netral": summary["netral"],
            "pos_ratio": summary["pos_ratio"],
            "neg_ratio": summary["neg_ratio"],
            "anomaly": "1" if anomaly else "0",
            "llm_provider": provider or "",
        }
    )
    rows.sort(key=lambda r: r.get("date", ""))
    with config.CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def notify_discord(
    date_str: str,
    summary: dict,
    verdict: dict,
    insight: dict | None,
) -> bool:
    """Kirim ringkasan ke Discord webhook. True bila terkirim."""
    url = config.DISCORD_WEBHOOK_URL
    if not url:
        return False

    lines = [
        f"**{config.APP_NAME} — {date_str}**",
        f"Total {summary['total']} ulasan | "
        f"positif {summary['pos_ratio'] * 100:.1f}% | "
        f"negatif {summary['neg_ratio'] * 100:.1f}%",
    ]
    if verdict.get("reasons"):
        lines.append("Pemicu: " + "; ".join(verdict["reasons"]))
    if insight:
        ringkas = insight.get("ringkasan") or insight.get("summary")
        if ringkas:
            lines.append(str(ringkas))
        for aksi in (insight.get("rekomendasi") or [])[:3]:
            lines.append(f"• {aksi}")
    content = "\n".join(lines)[:1900]

    payload = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return 200 <= resp.status < 300
    except Exception:  # noqa: BLE001 - notifikasi tidak boleh menggagalkan pipeline
        return False


GITHUB_API = "https://api.github.com"


def _github_post(url: str, payload: dict, token: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "sentimen-watch")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_issue_body(
    date_str: str, summary: dict, verdict: dict, insight: dict | None
) -> str:
    lines = [
        f"## Anomali sentimen — {config.APP_NAME} ({date_str})",
        "",
        "| Metrik | Nilai |",
        "| --- | --- |",
        f"| Total ulasan | {summary['total']} |",
        f"| Positif | {summary['positif']} ({summary['pos_ratio'] * 100:.1f}%) |",
        f"| Negatif | {summary['negatif']} ({summary['neg_ratio'] * 100:.1f}%) |",
        f"| Netral | {summary['netral']} |",
        "",
        "### Pemicu",
    ]
    for reason in verdict.get("reasons") or ["(tidak ada)"]:
        lines.append(f"- {reason}")

    if insight:
        lines += ["", "### Ringkasan AI", str(insight.get("ringkasan", ""))]
        if insight.get("tren"):
            lines += ["", f"**Tren:** {insight['tren']}"]
        rekomendasi = insight.get("rekomendasi") or []
        if rekomendasi:
            lines += ["", "### Rekomendasi"]
            for item in rekomendasi:
                if isinstance(item, dict):
                    lines.append(
                        f"- **{item.get('tindakan', '')}** — "
                        f"{item.get('alasan', '')} (prioritas {item.get('prioritas', '-')})"
                    )
                else:
                    lines.append(f"- {item}")

    lines += ["", "_Dibuat otomatis oleh pipeline Sentimen Watch._"]
    return "\n".join(lines)


def notify_github_issue(
    date_str: str, summary: dict, verdict: dict, insight: dict | None
) -> str | None:
    """Buat GitHub Issue saat anomali. Kembalikan URL issue bila berhasil."""
    token = config.GITHUB_TOKEN
    repo = config.GITHUB_REPOSITORY
    if not (token and repo):
        return None

    url = f"{GITHUB_API}/repos/{repo}/issues"
    title = (
        f"[Sentimen Watch] Anomali {date_str} — "
        f"negatif {summary['neg_ratio'] * 100:.1f}%"
    )
    body = build_issue_body(date_str, summary, verdict, insight)
    try:
        try:
            data = _github_post(url, {"title": title, "body": body, "labels": ["anomali"]}, token)
        except urllib.error.HTTPError as exc:
            if exc.code == 422:  # label belum ada -> kirim ulang tanpa label
                data = _github_post(url, {"title": title, "body": body}, token)
            else:
                raise
        return data.get("html_url")
    except Exception:  # noqa: BLE001 - notifikasi tidak boleh menggagalkan pipeline
        return None


def sheets_credentials():
    """Kredensial Sheets dari file path (lokal) atau isi JSON (GitHub Secret)."""
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    raw = config.GOOGLE_SERVICE_ACCOUNT_JSON
    if raw.strip().startswith("{"):
        return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
    return Credentials.from_service_account_file(raw, scopes=scopes)


def push_sheets(date_str: str, summary: dict, anomaly: bool, provider: str | None) -> bool:
    """Ekspor opsional ke Google Sheets (untuk dashboard Looker Studio)."""
    if not (config.GOOGLE_SERVICE_ACCOUNT_JSON and config.GOOGLE_SHEET_ID):
        return False
    try:
        import gspread

        client = gspread.authorize(sheets_credentials())
        sheet = client.open_by_key(config.GOOGLE_SHEET_ID).sheet1
        existing = sheet.get_all_values()
        if not existing:
            sheet.append_row(CSV_FIELDS)
        row = [
            date_str, summary["total"], summary["positif"], summary["negatif"],
            summary["netral"], summary["pos_ratio"], summary["neg_ratio"],
            "1" if anomaly else "0", provider or "",
        ]
        # ganti baris tanggal yang sama bila sudah ada
        dates = sheet.col_values(1)
        if date_str in dates:
            sheet.update(f"A{dates.index(date_str) + 1}", [row])
        else:
            sheet.append_row(row)
        return True
    except Exception:  # noqa: BLE001
        return False
