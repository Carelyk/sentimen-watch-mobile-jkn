"""Kirim SELURUH riwayat ke Google Sheets (sumber data Looker Studio).

Sekali jalan: menulis tab ``harian`` (dari data/sentiment_daily.csv) dan
tab ``bulanan`` (dari data/backfill/monthly.csv) ke spreadsheet.

Contoh:
    python -m pipeline.push_sheets
"""
from __future__ import annotations

import csv

from . import config, export


def _rows(path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh))


def _write_tab(sheet, title: str, rows: list[list[str]]):
    import gspread

    if not rows:
        return None
    try:
        ws = sheet.worksheet(title)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(
            title=title, rows=max(len(rows) + 20, 200), cols=max(len(rows[0]), 12)
        )
    ws.update(range_name="A1", values=rows)
    return ws


def main() -> int:
    if not (config.GOOGLE_SERVICE_ACCOUNT_JSON and config.GOOGLE_SHEET_ID):
        print(
            "Belum dikonfigurasi.\n"
            "Isi GOOGLE_SERVICE_ACCOUNT_JSON dan GOOGLE_SHEET_ID di .env "
            "(lihat docs/looker_studio.md)."
        )
        return 1

    import gspread

    sheet = gspread.authorize(export.sheets_credentials()).open_by_key(config.GOOGLE_SHEET_ID)

    daily = _rows(config.CSV_PATH)
    _write_tab(sheet, "harian", daily)
    print(f"[sheets] tab 'harian' : {len(daily) - 1} baris")

    monthly_path = config.DATA_DIR / "backfill" / "monthly.csv"
    if monthly_path.exists():
        monthly = _rows(monthly_path)
        _write_tab(sheet, "bulanan", monthly)
        print(f"[sheets] tab 'bulanan': {len(monthly) - 1} baris")

    print("[sheets] selesai. Lanjut: Looker Studio -> Create -> Data source -> Google Sheets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
