"""Fictional sample data for dry runs and tests. Company names are made up."""

import io
import zipfile


def _csv_utf16(rows: list[list[str]]) -> bytes:
    header = ["要素ID", "項目名", "コンテキストID", "相対年度", "連結・個別", "期間・時点", "ユニットID", "単位", "値"]
    lines = ["\t".join(header)] + ["\t".join(r) for r in rows]
    return ("\n".join(lines)).encode("utf-16")


def make_zip(rows: list[list[str]], name: str = "XBRL_TO_CSV/jpcrp-sample.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, _csv_utf16(rows))
    return buf.getvalue()


def _row(item: str, value: str) -> list[str]:
    return ["x", item, "FilingDateInstant", "当期", "その他", "時点", "", "", value]


SAMPLE_ZIPS = {
    "S100SMP1": make_zip([
        _row("会社名", "サンプル電機株式会社"),
        _row("英訳名", "Sample Denki Co., Ltd."),
        _row("証券コード", "99990"),
        _row("提出理由", "当社は、2026年11月5日開催の取締役会において、株式会社テスト工業の全株式を取得し子会社化することを決議しました。"),
        _row("取得価額", "1,200百万円"),
    ]),
    "S100SMP2": make_zip([
        _row("発行者の名称", "サンプル精機株式会社"),
        _row("証券コード", "99980"),
        _row("提出者の氏名又は名称", "Example Value Partners Ltd."),
        _row("株券等保有割合", "5.12%"),
        _row("保有目的", "純投資及び重要提案行為等を行うこと"),
    ], name="XBRL_TO_CSV/jplvh-sample.csv"),
}


def sample_documents(day: str) -> list[dict]:
    t = f"{day} 15:00"
    return [
        {"docID": "S100SMP1", "docTypeCode": "180", "secCode": "99990", "filerName": "サンプル電機株式会社",
         "docDescription": "臨時報告書", "submitDateTime": t, "csvFlag": "1", "englishDocFlag": "0",
         "withdrawalStatus": "0", "disclosureStatus": "0", "currentReportReason": "第19条第2項第8号の2"},
        {"docID": "S100SMP2", "docTypeCode": "350", "secCode": None, "filerName": "Example Value Partners Ltd.",
         "docDescription": "大量保有報告書", "submitDateTime": t, "csvFlag": "1", "englishDocFlag": "0",
         "withdrawalStatus": "0", "disclosureStatus": "0"},
        {"docID": "S100SMP3", "docTypeCode": "120", "secCode": "99970", "filerName": "対象外株式会社",
         "docDescription": "有価証券報告書", "submitDateTime": t, "csvFlag": "1", "englishDocFlag": "1",
         "withdrawalStatus": "0", "disclosureStatus": "0"},
        {"docID": "S100SMP4", "docTypeCode": "240", "secCode": None, "filerName": "サンプルホールディングス株式会社",
         "docDescription": "公開買付届出書", "submitDateTime": t, "csvFlag": "0", "englishDocFlag": "1",
         "withdrawalStatus": "1", "disclosureStatus": "0"},
    ]


def sample_fetch(doc_id: str) -> bytes:
    return SAMPLE_ZIPS[doc_id]
