"""EDINET API v2 client (official API only; scraping the EDINET website is prohibited by its terms).

Docs: https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0030.html
"""

import csv
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from .config import DOC_TYPES

BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"
USER_AGENT = "jp-filings-digest/0.1"


class EdinetError(RuntimeError):
    pass


def _get(url: str, params: dict, retries: int = 3, timeout: int = 60) -> bytes:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.read()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code != 429 and exc.code < 500:
                break  # 4xx such as a bad key: retrying will not help
            time.sleep(5 * (attempt + 1))
        except Exception as exc:  # network errors
            last = exc
            time.sleep(5 * (attempt + 1))
    raise EdinetError(f"GET failed after {retries} tries: {url} ({last})")


def list_documents(date: str, api_key: str) -> list[dict]:
    """All filings submitted on `date` (YYYY-MM-DD), with metadata."""
    raw = _get(f"{BASE_URL}/documents.json", {"date": date, "type": 2, "Subscription-Key": api_key})
    data = json.loads(raw.decode("utf-8"))
    status = str(data.get("metadata", {}).get("status", ""))
    if status and status != "200":
        raise EdinetError(f"EDINET returned status {status}: {data.get('metadata', {}).get('message')}")
    return data.get("results") or []


def fetch_csv_zip(doc_id: str, api_key: str) -> bytes:
    """The XBRL-to-CSV package (type=5) of one filing."""
    return _get(f"{BASE_URL}/documents/{doc_id}", {"type": 5, "Subscription-Key": api_key})


def select_documents(docs: list[dict], max_docs: int) -> list[dict]:
    """Keep filing types we cover, drop withdrawn ones, put no-English and urgent ones first."""
    picked = []
    for d in docs:
        code = str(d.get("docTypeCode") or "")
        if code not in DOC_TYPES:
            continue
        if str(d.get("withdrawalStatus") or "0") != "0":
            continue
        if str(d.get("disclosureStatus") or "0") not in ("0", ""):
            continue
        picked.append(d)

    def key(d):
        no_english = 0 if str(d.get("englishDocFlag") or "0") == "0" else 1
        return (DOC_TYPES[str(d["docTypeCode"])][1], no_english, d.get("submitDateTime") or "")

    picked.sort(key=key)
    return picked[:max_docs]


def parse_csv_zip(blob: bytes, max_chars: int = 12000) -> str:
    """Turn the CSV package into 'item: value' lines for the summarizer.

    EDINET CSVs are UTF-16 and tab-separated, with columns such as
    要素ID, 項目名, コンテキストID, 相対年度, 連結・個別, 期間・時点, ユニットID, 単位, 値.
    """
    lines: list[str] = []
    seen = set()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = sorted(n for n in z.namelist() if n.endswith(".csv"))
        for name in names:
            raw = z.read(name)
            text = None
            for enc in ("utf-16", "utf-8-sig", "cp932"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                continue
            reader = csv.reader(io.StringIO(text), delimiter="\t")
            header = next(reader, None) or []
            def col(name, fallback):
                return header.index(name) if name in header else fallback
            i_name, i_val = col("項目名", 1), col("値", 8)
            i_ctx, i_year, i_unit = col("コンテキストID", 2), col("相対年度", 3), col("単位", 7)
            for row in reader:
                if len(row) <= max(i_name, i_val):
                    continue
                item, val = row[i_name].strip(), row[i_val].strip()
                if not val or val in ("－", "-") or (item, val) in seen:
                    continue
                seen.add((item, val))
                # keep which period/context a number belongs to (e.g. previous vs current holding ratio)
                ctx = " / ".join(x for x in (
                    row[i_year].strip() if len(row) > i_year else "",
                    row[i_ctx].strip() if len(row) > i_ctx else "",
                ) if x)
                unit = row[i_unit].strip() if len(row) > i_unit else ""
                lines.append(f"{item} [{ctx}]: {val}{(' ' + unit) if unit else ''}" if ctx else f"{item}: {val}")
    out = "\n".join(lines)
    return out[:max_chars]


def edinet_viewer_url(doc_id: str) -> str:
    """Link readers to the official filing (PDF of the original)."""
    return f"https://disclosure2dl.edinet-fsa.go.jp/searchdocument/pdf/{doc_id}.pdf"
