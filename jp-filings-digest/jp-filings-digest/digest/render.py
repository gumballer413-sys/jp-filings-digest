"""Static site (GitHub Pages), RSS feed and weekly newsletter text."""

import html as _html
import json
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

from .config import Settings


def esc(v) -> str:
    return _html.escape('' if v is None else str(v))

PDL_URL = "https://www.digital.go.jp/resources/open_data/public_data_license_v1.0"
EDINET_URL = "https://disclosure2.edinet-fsa.go.jp/"
EDINET_TERMS_URL = "https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0030.html"
JST = timezone(timedelta(hours=9))

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#5f6368;--line:#e4e1da;--accent:#9b2c2c}
@media (prefers-color-scheme:dark){:root{--bg:#141414;--fg:#ececec;--muted:#a0a0a0;--line:#2c2c2c;--accent:#f08a7e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.1rem;margin:32px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.sub{color:var(--muted);margin:0 0 24px}.item{padding:14px 0;border-bottom:1px solid var(--line)}
.meta{color:var(--muted);font-size:.85rem}.tag{display:inline-block;font-size:.75rem;border:1px solid var(--line);border-radius:4px;padding:0 6px;margin-right:6px}
.tag.noen{border-color:var(--accent);color:var(--accent)}ul{margin:6px 0 0 18px;padding:0}a{color:var(--accent)}
footer{margin-top:40px;color:var(--muted);font-size:.8rem;border-top:1px solid var(--line);padding-top:12px}
.cta{margin:16px 0;padding:12px;border:1px solid var(--line);border-radius:8px}
"""


def footer_html(s: Settings) -> str:
    contact = f' Contact: {esc(s.contact_email)}.' if s.contact_email else ""
    return (
        "<footer>"
        f'Source: <a href="{EDINET_URL}">EDINET</a> (Financial Services Agency of Japan; <a href="{EDINET_TERMS_URL}">terms</a>), used under the '
        f'<a href="{PDL_URL}">Public Data License 1.0 (PDL1.0)</a>. '
        f"The original filings were translated and summarized with AI and edited by {esc(s.operator_name)}; "
        "this is not an official government publication. Always check the original filing linked on each item. "
        "This site reports facts from public filings only and is not investment advice."
        f"{contact}</footer>"
    )


def item_html(it: dict) -> str:
    facts = "".join(f"<li>{esc(str(f))}</li>" for f in it.get("key_facts", [])[:5])
    purpose = it.get("stated_purpose")
    purpose_html = (
        f'<div class="meta">Stated purpose: {esc(purpose)}</div>'
        if purpose and purpose != "Not stated" else ""
    )
    noen = '<span class="tag noen">Japanese only on EDINET</span>' if it.get("no_english") else ""
    code = it.get("securities_code")
    code_html = f" ({esc(code)})" if code and not str(code).startswith("Not") else ""
    return (
        f'<div class="item" id="{esc(it.get("doc_id", ""))}">'
        f'<span class="tag">{esc(it.get("type_label", ""))}</span>{noen}'
        f'<div><strong>{esc(it.get("company", ""))}{code_html}</strong> — {esc(it.get("headline", ""))}</div>'
        f"<ul>{facts}</ul>{purpose_html}"
        f'<div class="meta">Filed by {esc(it.get("filer", ""))} · {esc(it.get("submitted", ""))} · '
        f'<a href="{esc(it.get("source_url", ""))}">Original filing (Japanese)</a></div>'
        "</div>"
    )


def page(title: str, body: str, s: Settings) -> str:
    cta = (
        f'<div class="cta">Get the weekly English digest by email: <a href="{esc(s.subscribe_url)}">subscribe free</a></div>'
        if s.subscribe_url else ""
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><link rel='alternate' type='application/rss+xml' href='feed.xml'>"
        f"<style>{CSS}</style></head><body><main>{body}{cta}{footer_html(s)}</main></body></html>"
    )


def _is_company_news(it: dict) -> bool:
    """Hide fund reports saved before the fund filter existed (no 4-character securities code)."""
    if it.get("doc_type") not in ("180", "220"):
        return True
    code = str(it.get("securities_code") or "")
    return len(code) >= 4 and code[:4].isalnum() and not code.startswith("Not")


def _code4(code) -> str:
    code = str(code or "")
    return code[:4] if len(code) == 5 and code.endswith("0") else code


def load_days(data_dir: Path) -> dict[str, list[dict]]:
    days = {}
    for f in sorted(data_dir.glob("*.json")):
        items = [it for it in json.loads(f.read_text(encoding="utf-8")) if _is_company_news(it)]
        for it in items:
            it["securities_code"] = _code4(it.get("securities_code"))
        days[f.stem] = items
    return days


def render_site(out_dir: Path, s: Settings, recent: int = 30) -> None:
    data_dir = out_dir / "data"
    days = load_days(data_dir)
    (out_dir / "daily").mkdir(parents=True, exist_ok=True)
    for d, items in days.items():
        body = (
            f"<h1>{esc(s.site_title)}</h1><p class='sub'><a href='../index.html'>All days</a> · "
            f"Filings submitted on {d} (JST) · {len(items)} items</p>"
            + "".join(item_html(it) for it in items)
        )
        (out_dir / "daily" / f"{d}.html").write_text(page(f"{d} · {s.site_title}", body, s).replace("href='feed.xml'", "href='../feed.xml'"), encoding="utf-8")

    links = "".join(
        f"<div class='item'><a href='daily/{d}.html'>{d}</a> <span class='meta'>{len(days[d])} filings</span></div>"
        for d in sorted(days, reverse=True)[:recent]
    )
    intro = (
        f"<h1>{esc(s.site_title)}</h1><p class='sub'>Tender offers, 5% stake reports, extraordinary reports and buybacks "
        "filed by Japanese companies, summarized in English every business day. Filings with no English version on EDINET are marked.</p>"
    )
    (out_dir / "index.html").write_text(page(s.site_title, intro + links, s), encoding="utf-8")
    write_feed(out_dir, days, s)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")


def write_feed(out_dir: Path, days: dict[str, list[dict]], s: Settings, limit: int = 100) -> None:
    entries = []
    for d in sorted(days, reverse=True):
        for it in days[d]:
            entries.append((d, it))
    entries = entries[:limit]
    items_xml = []
    for d, it in entries:
        dt = datetime.fromisoformat(d).replace(hour=18, tzinfo=JST)
        desc = " | ".join(str(f) for f in it.get("key_facts", []))
        items_xml.append(
            "<item>"
            f"<title>{esc(it.get('company', ''))}: {esc(it.get('headline', ''))}</title>"
            f"<link>{esc(s.site_url.rstrip('/'))}/daily/{d}.html#{esc(it.get('doc_id', ''))}</link>"
            f"<guid isPermaLink='false'>{esc(it.get('doc_id', ''))}</guid>"
            f"<pubDate>{format_datetime(dt)}</pubDate>"
            f"<description>{esc(desc)} (Source: EDINET, PDL1.0. Not investment advice.)</description>"
            "</item>"
        )
    xml = (
        "<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel>"
        f"<title>{esc(s.site_title)}</title><link>{esc(s.site_url)}</link>"
        "<description>English fact summaries of Japanese corporate filings from EDINET.</description>"
        + "".join(items_xml) + "</channel></rss>"
    )
    (out_dir / "feed.xml").write_text(xml, encoding="utf-8")


def weekly_markdown(out_dir: Path, s: Settings, end: date, days_back: int = 7, top: int = 15) -> str:
    """Newsletter text for the free weekly digest. Paste into the newsletter service, or send by API."""
    days = load_days(out_dir / "data")
    start = end - timedelta(days=days_back - 1)
    picked = []
    for d, items in days.items():
        if start.isoformat() <= d <= end.isoformat():
            picked.extend(items)
    picked.sort(key=lambda it: (it.get("priority", 9), 0 if it.get("no_english") else 1))
    lines = [
        f"# {s.site_title}: week of {start.isoformat()} to {end.isoformat()}",
        "",
        f"{len(picked)} filings covered this week. Here are {min(top, len(picked))} of them, tender offers first.",
        "",
    ]
    for it in picked[:top]:
        code = it.get("securities_code")
        code_txt = f" ({code})" if code and not str(code).startswith("Not") else ""
        tag = " [Japanese only on EDINET]" if it.get("no_english") else ""
        lines.append(f"**{it.get('company')}{code_txt}**{tag}: {it.get('headline')}")
        for f in it.get("key_facts", [])[:3]:
            lines.append(f"- {f}")
        lines.append(f"- [Original filing]({it.get('source_url')})")
        lines.append("")
    lines += [
        "---",
        f"Full daily list: {s.site_url}",
        "",
        "Source: EDINET (Financial Services Agency of Japan), PDL1.0. Translated and summarized with AI and edited by "
        f"{s.operator_name}; not an official government publication. Facts only, not investment advice.",
    ]
    return "\n".join(lines)
