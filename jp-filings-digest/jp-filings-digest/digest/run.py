"""Daily job: python -m digest.run [--date YYYY-MM-DD] [--mock] [--out docs]

Weekly digest: python -m digest.run --weekly [--date YYYY-MM-DD]
"""

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import edinet, render, summarize
from .config import DOC_TYPES, Settings

JST = timezone(timedelta(hours=9))


def build_item(meta: dict, summary: dict) -> dict:
    code = str(meta.get("docTypeCode"))
    label, priority = DOC_TYPES.get(code, ("Filing", 9))
    return {
        "doc_id": meta.get("docID"),
        "doc_type": code,
        "type_label": label,
        "priority": priority,
        "no_english": str(meta.get("englishDocFlag") or "0") == "0",
        "submitted": meta.get("submitDateTime") or "",
        "source_url": edinet.edinet_viewer_url(meta.get("docID", "")),
        "company": summary.get("company", "Not stated"),
        "securities_code": summary.get("securities_code", "Not stated"),
        "filer": summary.get("filer", meta.get("filerName", "")),
        "event": summary.get("event", "other"),
        "headline": summary.get("headline", ""),
        "key_facts": summary.get("key_facts", [])[:5],
        "stated_purpose": summary.get("stated_purpose", "Not stated"),
        "needs_review": summary.get("needs_review", False),
    }


def run_daily(day: str, out_dir: Path, s: Settings, mock: bool = False,
              docs: list[dict] | None = None, fetch=None) -> dict:
    """Process one day. `docs` and `fetch` can be injected for tests."""
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    day_file = data_dir / f"{day}.json"
    existing = json.loads(day_file.read_text(encoding="utf-8")) if day_file.exists() else []
    done = {it["doc_id"] for it in existing}

    if docs is None:
        if not s.edinet_api_key:
            raise SystemExit("EDINET_API_KEY is not set (use --mock for a dry run with sample data).")
        docs = edinet.list_documents(day, s.edinet_api_key)
    fetch = fetch or (lambda doc_id: edinet.fetch_csv_zip(doc_id, s.edinet_api_key))

    selected = [d for d in edinet.select_documents(docs, s.max_docs) if d.get("docID") not in done]
    stats = {"listed": len(docs), "selected": len(selected), "summarized": 0, "errors": 0,
             "needs_review": 0, "input_tokens": 0, "output_tokens": 0}
    items = list(existing)
    review: list[dict] = []
    for meta in selected:
        try:
            body = ""
            if str(meta.get("csvFlag") or "0") == "1":
                body = edinet.parse_csv_zip(fetch(meta["docID"]), s.max_input_chars)
                if not mock:
                    time.sleep(s.request_interval_sec)  # be polite to the EDINET API
            summ = summarize.summarize(meta, body, s.anthropic_api_key, s.model, mock=mock)
            usage = summ.get("usage") or {}
            stats["input_tokens"] += int(usage.get("input_tokens") or 0)
            stats["output_tokens"] += int(usage.get("output_tokens") or 0)
            item = build_item(meta, summ)
            if item["needs_review"]:
                stats["needs_review"] += 1
                review.append(item)
                continue  # never publish advice-like wording; it stays out until a human checks it
            items.append(item)
            stats["summarized"] += 1
        except Exception as exc:  # one bad filing must not stop the day
            stats["errors"] += 1
            print(f"[warn] {meta.get('docID')}: {exc}", file=sys.stderr)

    items.sort(key=lambda it: (it.get("priority", 9), 0 if it.get("no_english") else 1, it.get("submitted", "")))
    day_file.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    if review:  # kept outside the published site for a human to check
        rdir = out_dir.parent / "needs_review"
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / f"{day}.json").write_text(json.dumps(review, ensure_ascii=False, indent=1), encoding="utf-8")
    render.render_site(out_dir, s)
    return stats


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="EDINET -> English fact summaries")
    p.add_argument("--date", help="YYYY-MM-DD (JST). Default: today in JST")
    p.add_argument("--out", default="docs", help="output folder served by GitHub Pages")
    p.add_argument("--mock", action="store_true", help="no API calls; use the bundled sample data")
    p.add_argument("--weekly", action="store_true", help="write the weekly newsletter text instead")
    a = p.parse_args(argv)

    s = Settings()
    day = a.date or datetime.now(JST).date().isoformat()
    out = Path(a.out)

    if a.weekly:
        text = render.weekly_markdown(out, s, date.fromisoformat(day))
        (out / "weekly").mkdir(parents=True, exist_ok=True)
        path = out / "weekly" / f"{day}.md"
        path.write_text(text, encoding="utf-8")
        print(f"weekly digest written: {path}")
        return 0

    if a.mock:
        from .sample import sample_documents, sample_fetch
        stats = run_daily(day, out, s, mock=True, docs=sample_documents(day), fetch=sample_fetch)
        print(json.dumps(stats, ensure_ascii=False))
        return 0

    if s.operator_name == "the operator of this site":
        raise SystemExit("Set OPERATOR_NAME: PDL1.0 requires naming who edited the data.")
    days = [day]
    if not a.date:  # also catch filings that arrived after yesterday's run
        prev = date.fromisoformat(day) - timedelta(days=1)
        while prev.weekday() >= 5:
            prev -= timedelta(days=1)
        days.insert(0, prev.isoformat())
    for d in days:
        stats = run_daily(d, out, s)
        cost = stats["input_tokens"] / 1e6 * 0.10 + stats["output_tokens"] / 1e6 * 0.50
        print(d, json.dumps({**stats, "estimated_usd_haiku_5_5": round(cost, 4)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
