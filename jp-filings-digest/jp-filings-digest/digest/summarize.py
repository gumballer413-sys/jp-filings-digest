"""Turn one Japanese filing into a short English fact summary with Claude (or a mock for tests)."""

import json
import re
import time
import urllib.error
import urllib.request

from .config import BANNED_PHRASES, DOC_TYPES

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You translate Japanese regulatory filings from EDINET into short English fact summaries for overseas readers.

Rules you must follow:
- Use only facts written in the filing text you are given. Never add outside knowledge, context or guesses.
- No opinions, predictions, ratings or advice. Never say whether to buy, sell or hold, and never call anything cheap, attractive, risky, an opportunity, positive or negative.
- Keep numbers, percentages, dates and share counts exactly as written. Convert Japanese dates to YYYY-MM-DD.
- Write company and person names in their official English name if the filing gives one, otherwise in romaji.
- If a field is not in the text, write "Not stated".

Reply with JSON only, in this shape:
{"company": "...", "securities_code": "4 or 5 characters, or Not stated", "filer": "...",
 "event": "one of: tender_offer, tender_offer_result, tender_offer_opinion, extraordinary_report, large_shareholding, buyback_status, other",
 "headline": "a plain factual sentence of at most 16 words",
 "key_facts": ["up to 5 short facts, each with its number where there is one"],
 "stated_purpose": "for 5% reports and tender offers, the purpose as stated in the filing, else Not stated"}"""


def _banned_hits(text: str) -> list[str]:
    low = text.lower()
    return [p for p in BANNED_PHRASES if re.search(rf"\b{re.escape(p)}\b", low)]


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no JSON object in model reply")
    return json.loads(text[start : end + 1])


class ModelError(RuntimeError):
    pass


def _call_claude(api_key: str, model: str, user_text: str, max_tokens: int = 2000) -> tuple[str, dict]:
    """One Messages API call with retries on 429/5xx. Raises if the reply was cut off."""
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_text}],
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    data = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                data = json.loads(res.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            raise ModelError(f"Claude API {exc.code}: {detail}") from exc
    if data.get("stop_reason") == "max_tokens":
        raise ModelError("reply was cut off at max_tokens")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return text, data.get("usage", {})


def build_user_text(meta: dict, body_text: str) -> str:
    label = DOC_TYPES.get(str(meta.get("docTypeCode")), ("Filing", 9))[0]
    return (
        f"Filing type: {label}\n"
        f"EDINET description: {meta.get('docDescription')}\n"
        f"Filer: {meta.get('filerName')}\n"
        f"Securities code in metadata: {meta.get('secCode') or 'none'}\n"
        f"Submitted: {meta.get('submitDateTime')}\n"
        f"Reason category (extraordinary reports): {meta.get('currentReportReason') or 'none'}\n"
        "---- filing text (item: value) ----\n"
        f"{body_text or '(no machine-readable text; summarize from the metadata only)'}"
    )


def _clean(result: dict, meta: dict) -> dict:
    """Force the model's reply into the expected types so rendering can never crash."""
    def s(v, default="Not stated"):
        return str(v).strip() if v not in (None, "") else default
    facts = result.get("key_facts") or []
    if isinstance(facts, str):
        facts = [facts]
    return {
        "company": s(result.get("company"), s(meta.get("filerName"))),
        "securities_code": s(result.get("securities_code"))[:5],
        "filer": s(result.get("filer"), s(meta.get("filerName"))),
        "event": s(result.get("event"), "other"),
        "headline": s(result.get("headline"), "Filing submitted to EDINET"),
        "key_facts": [str(f).strip() for f in facts if str(f).strip()][:5],
        "stated_purpose": s(result.get("stated_purpose")),
    }


def mock_summary(meta: dict) -> dict:
    """Deterministic stand-in used in tests and dry runs. No API call."""
    label = DOC_TYPES.get(str(meta.get("docTypeCode")), ("Filing", 9))[0]
    return {
        "company": meta.get("filerName") or "Not stated",
        "securities_code": str(meta.get("secCode"))[:4] if meta.get("secCode") else "Not stated",
        "filer": meta.get("filerName") or "Not stated",
        "event": "other",
        "headline": f"{label} filed on EDINET",
        "key_facts": [f"EDINET description: {meta.get('docDescription')}"],
        "stated_purpose": "Not stated",
    }


def summarize(meta: dict, body_text: str, api_key: str, model: str, mock: bool = False) -> dict:
    """Return a summary dict. Adds 'needs_review' when the guard found advice-like wording."""
    if mock or not api_key:
        result = mock_summary(meta)
        result["needs_review"] = False
        result["usage"] = {}
        return result

    user_text = build_user_text(meta, body_text)
    reply, usage = _call_claude(api_key, model, user_text)
    result = _clean(_extract_json(reply), meta)
    hits = _banned_hits(json.dumps(result, ensure_ascii=False))
    if hits:  # one retry with an explicit reminder, then flag for a human
        reply, usage2 = _call_claude(
            api_key, model,
            user_text + f"\n\nYour previous answer used advice-like words {hits}. Rewrite with facts only.",
        )
        result = _clean(_extract_json(reply), meta)
        usage = {
            k: (usage.get(k) or 0) + (usage2.get(k) or 0)
            for k in set(usage) | set(usage2)
            if isinstance(usage.get(k, 0), int) and isinstance(usage2.get(k, 0), int)
        }
        hits = _banned_hits(json.dumps(result, ensure_ascii=False))
    result["needs_review"] = bool(hits)
    result["usage"] = usage
    return result
