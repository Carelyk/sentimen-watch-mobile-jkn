"""Panggil LLM untuk *menarasikan* angka yang sudah dihitung.

Urutan: Gemini (utama) -> Groq (fallback). Keduanya dipanggil lewat REST biasa
(tanpa SDK) supaya ringan dan tidak terikat versi paket.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from . import config

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq berada di belakang Cloudflare; User-Agent bawaan urllib diblokir (error 1010).
USER_AGENT = "sentimen-watch/1.0 (+https://github.com/Carelyk/sentimen-watch-mobile-jkn)"


# --- Template ---------------------------------------------------------------
def load_prompt(name: str = "data_analyst.md") -> str:
    return (config.PROMPTS_DIR / name).read_text(encoding="utf-8")


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render(template: str, values: dict[str, Any]) -> str:
    """Isi ``{variabel}`` saja, biarkan kurung JSON ({"...": ...}) apa adanya."""

    def repl(match: re.Match) -> str:
        key = match.group(1)
        return str(values[key]) if key in values else match.group(0)

    return _PLACEHOLDER_RE.sub(repl, template)


def build_prompt(
    date_str: str,
    summary: dict[str, Any],
    baseline: dict[str, Any],
    verdict: dict[str, Any],
) -> str:
    template = load_prompt("data_analyst.md")
    ringkasan = {
        "periode": date_str,
        "sumber_data": f"ulasan pengguna aplikasi {config.APP_NAME} di Google Play Store",
        "ringkasan": summary,
        "baseline": baseline,
        "pemicu_anomali": verdict.get("reasons", []),
    }
    return render(
        template,
        {
            "sumber_data": ringkasan["sumber_data"],
            "periode": date_str,
            "baseline_hari": config.BASELINE_DAYS,
            "audiens": "manajemen produk",
            "ringkasan_json": json.dumps(ringkasan, ensure_ascii=False, indent=2),
        },
    )


# --- Pemanggilan provider ---------------------------------------------------
def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", USER_AGENT)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_gemini(prompt: str) -> str:
    url = GEMINI_URL.format(model=config.GEMINI_MODEL, key=config.GEMINI_API_KEY)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
    }
    data = _post_json(url, payload)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_groq(prompt: str) -> str:
    payload = {
        "model": config.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
    data = _post_json(GROQ_URL, payload, headers)
    return data["choices"][0]["message"]["content"]


def _available(name: str) -> bool:
    return bool(config.GEMINI_API_KEY if name == "gemini" else config.GROQ_API_KEY)


def _call(name: str, prompt: str) -> str:
    return call_gemini(prompt) if name == "gemini" else call_groq(prompt)


def provider_order() -> list[str]:
    """Urutan provider sesuai LLM_PRIMARY (default groq -> gemini)."""
    return ["gemini", "groq"] if config.LLM_PRIMARY == "gemini" else ["groq", "gemini"]


def call_llm(prompt: str) -> dict[str, Any]:
    """Coba provider sesuai urutan, fallback ke berikutnya. {provider, text, errors}."""
    errors: list[str] = []
    for name in provider_order():
        if not _available(name):
            continue
        try:
            return {"provider": name, "text": _call(name, prompt), "errors": errors}
        except Exception as exc:  # noqa: BLE001 - laporkan dan lanjut ke fallback
            errors.append(f"{name}: {exc}")
    if not errors:
        errors.append("tidak ada kunci LLM (GEMINI_API_KEY / GROQ_API_KEY kosong)")
    return {"provider": None, "text": None, "errors": errors}


# --- Parsing hasil ----------------------------------------------------------
def parse_json(text: str | None) -> dict | None:
    if not text:
        return None
    clean = text.strip()
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.MULTILINE).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass
    start, end = clean.find("{"), clean.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(clean[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None
