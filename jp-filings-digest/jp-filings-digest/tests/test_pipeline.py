import json
from datetime import date
from pathlib import Path

from digest import edinet, render, summarize
from digest.config import Settings
from digest.run import run_daily
from digest.sample import SAMPLE_ZIPS, sample_documents, sample_fetch

DAY = "2026-11-05"


def settings(**kw) -> Settings:
    s = Settings()
    s.edinet_api_key = ""
    s.anthropic_api_key = ""
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def test_select_keeps_covered_types_and_drops_withdrawn():
    picked = edinet.select_documents(sample_documents(DAY), max_docs=10)
    ids = [d["docID"] for d in picked]
    assert ids == ["S100SMP1", "S100SMP2"]  # 有報 not covered, withdrawn TOB dropped; 180 before 350


def test_max_docs_cap():
    assert len(edinet.select_documents(sample_documents(DAY), max_docs=1)) == 1


def test_parse_utf16_csv_zip():
    text = edinet.parse_csv_zip(SAMPLE_ZIPS["S100SMP2"])
    assert "株券等保有割合" in text and "5.12%" in text
    assert "純投資及び重要提案行為等を行うこと" in text


def test_banned_phrase_guard():
    assert summarize._banned_hits("This stock is undervalued and you should buy.") == ["undervalued"] or \
        "undervalued" in summarize._banned_hits("This stock is undervalued and you should buy.")
    assert summarize._banned_hits("Status report on the share buyback program") == []
    assert summarize._banned_hits("A tender offer to acquire all shares") == []


def test_extract_json_from_fenced_reply():
    reply = 'Here:\n```json\n{"company": "A", "key_facts": ["x"]}\n```'
    assert summarize._extract_json(reply)["company"] == "A"


def test_needs_review_items_are_not_published(tmp_path, monkeypatch):
    def fake_call(api_key, model, user_text, max_tokens=2000):
        return json.dumps({"company": "X", "headline": "Shares look undervalued", "key_facts": []}), \
            {"input_tokens": 10, "output_tokens": 5}
    monkeypatch.setattr(summarize, "_call_claude", fake_call)
    s = settings(anthropic_api_key="test-key", request_interval_sec=0)
    stats = run_daily(DAY, tmp_path, s, mock=False, docs=sample_documents(DAY), fetch=sample_fetch)
    assert stats["needs_review"] == 2 and stats["summarized"] == 0
    assert json.loads((tmp_path / "data" / f"{DAY}.json").read_text()) == []


def test_end_to_end_mock_builds_site_and_feed(tmp_path):
    s = settings(site_url="https://example.github.io/x", subscribe_url="https://example.com/sub")
    stats = run_daily(DAY, tmp_path, s, mock=True, docs=sample_documents(DAY), fetch=sample_fetch)
    assert stats["summarized"] == 2 and stats["errors"] == 0
    index = (tmp_path / "index.html").read_text()
    daily = (tmp_path / "daily" / f"{DAY}.html").read_text()
    feed = (tmp_path / "feed.xml").read_text()
    assert "PDL1.0" in daily and "not investment advice" in daily
    assert "No English filing" in daily
    assert f"daily/{DAY}.html" in index
    assert feed.count("<item>") == 2


def test_rerun_skips_done_documents(tmp_path):
    s = settings()
    run_daily(DAY, tmp_path, s, mock=True, docs=sample_documents(DAY), fetch=sample_fetch)
    stats = run_daily(DAY, tmp_path, s, mock=True, docs=sample_documents(DAY), fetch=sample_fetch)
    assert stats["selected"] == 0
    assert len(json.loads((tmp_path / "data" / f"{DAY}.json").read_text())) == 2


def test_weekly_markdown(tmp_path):
    s = settings()
    run_daily(DAY, tmp_path, s, mock=True, docs=sample_documents(DAY), fetch=sample_fetch)
    md = render.weekly_markdown(tmp_path, s, date.fromisoformat(DAY))
    assert "2 filings covered this week" in md
    assert "[no English filing]" in md and "not investment advice" in md


def test_recommend_is_allowed_for_tender_offer_opinions():
    assert summarize._banned_hits("The board recommended that shareholders tender their shares.") == []


def test_clean_survives_bad_model_output():
    out = summarize._clean({"headline": None, "key_facts": "one fact", "company": ""}, {"filerName": "F"})
    assert out["headline"] and out["key_facts"] == ["one fact"] and out["company"] == "F"


def test_needs_review_saved_outside_site(tmp_path, monkeypatch):
    def fake_call(api_key, model, user_text, max_tokens=2000):
        return json.dumps({"company": "X", "headline": "Shares look undervalued", "key_facts": []}), {}
    monkeypatch.setattr(summarize, "_call_claude", fake_call)
    site = tmp_path / "docs"
    run_daily(DAY, site, settings(anthropic_api_key="k", request_interval_sec=0),
              docs=sample_documents(DAY), fetch=sample_fetch)
    assert (tmp_path / "needs_review" / f"{DAY}.json").exists()


def test_csv_lines_keep_context():
    text = edinet.parse_csv_zip(SAMPLE_ZIPS["S100SMP2"])
    assert "[当期 / FilingDateInstant]" in text
