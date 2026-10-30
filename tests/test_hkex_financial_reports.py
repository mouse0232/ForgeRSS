#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytz
import pytest

from generators.finance.hkex_financial_reports import (
    DEFAULT_T2_CODES,
    HKEX_HOST,
    PAGE_CAPACITY,
    HkexFinancialReportsGenerator,
    normalize_stock_code,
    parse_rel_time,
    safe_filename,
    split_t2_codes,
)

HK_TZ = pytz.timezone("Asia/Hong_Kong")


ANNUAL_REPORT = {
    "newsId": 12380001,
    "title": "2025 Annual Report",
    "lTxt": "財務報表/環境、社會及管治資料 - [年報]",
    "sTxt": "財務報表/環境、社會及管治資料 - [年報]",
    "ext": "pdf",
    "size": "334KB",
    "webPath": "/listedco/listconews/sehk/2026/1028/2026102800024_c.pdf",
    "market": "SEHK",
    "multi": 0,
    "stock": [{"sc": "00700", "sn": "騰訊控股"}],
    "relTime": "28/10/2026 06:33",
    "t1Code": "40000",
    "t2Code": "40100",
    "dod": "N",
    "dodPath": "NaN",
}

QUARTERLY_RESULTS = {
    "newsId": 12380002,
    "title": "2026年第三季度業績",
    "lTxt": "公告及通告 - [季度業績]",
    "sTxt": "公告及通告 - [季度業績]",
    "ext": "pdf",
    "size": "1MB",
    "webPath": "/listedco/listconews/sehk/2026/1028/2026102800100_c.pdf",
    "market": "SEHK",
    "multi": 0,
    "stock": [{"sc": "00941", "sn": "中國移動"}],
    "relTime": "28/10/2026 09:00",
    "t1Code": "10000",
    "t2Code": "13600",
    "dod": "N",
    "dodPath": "NaN",
}

MULTI_STOCK_HTM = {
    "newsId": 12380003,
    "title": "全球發售",
    "lTxt": "上市文件 - [發售以供認購]",
    "sTxt": "上市文件 - [發售以供認購]",
    "ext": "htm",
    "size": "88KB",
    "webPath": "/listedco/listconews/sehk/2026/1028/2026102800200_c.htm",
    "market": "SEHK",
    "multi": 1,
    "stock": [
        {"sc": "03690", "sn": "美團－Ｗ"},
        {"sc": "83690", "sn": "美團－ＷＲ"},
    ],
    "relTime": "28/10/2026 18:00",
    "t1Code": "30000",
    "t2Code": "30700",
    "dod": "N",
    "dodPath": "NaN",
}

PROSPECTUS = {
    "newsId": 12380005,
    "title": "全球發售",
    "lTxt": "上市文件 - [發售以供認購]",
    "sTxt": "上市文件 - [發售以供認購]",
    "ext": "pdf",
    "size": "12MB",
    "webPath": "/listedco/listconews/sehk/2026/1030/2026103000100_c.pdf",
    "market": "SEHK",
    "multi": 0,
    "stock": [{"sc": "07672", "sn": "芯德半導體"}],
    "relTime": "30/10/2026 06:23",
    "t1Code": "30000",
    "t2Code": "30700",
    "dod": "N",
    "dodPath": "NaN",
}

INTRODUCTION_LISTING = {
    "newsId": 12380006,
    "title": "以介紹方式於香港聯合交易所有限公司主板上市",
    "lTxt": "上市文件 - [介紹]",
    "sTxt": "上市文件 - [介紹]",
    "ext": "pdf",
    "size": "8MB",
    "webPath": "/listedco/listconews/sehk/2026/1030/2026103000200_c.pdf",
    "market": "SEHK",
    "stock": [{"sc": "01821", "sn": "中旅港澳"}],
    "relTime": "30/10/2026 07:14",
    "t1Code": "30000",
    "t2Code": "30500",
}

MISSING_WEBPATH = {
    "newsId": 12380004,
    "title": "中期報告",
    "lTxt": "財務報表/環境、社會及管治資料 - [中期/半年度報告]",
    "ext": "pdf",
    "size": "2MB",
    "webPath": "",
    "market": "SEHK",
    "stock": [{"sc": "00005", "sn": "匯豐控股"}],
    "relTime": "27/10/2026 12:00",
    "t1Code": "40000",
    "t2Code": "40200",
}

SUSPENSION = {
    "newsId": 12380999,
    "title": "暫停買賣",
    "lTxt": "公告及通告 - [暫停買賣]",
    "ext": "pdf",
    "size": "20KB",
    "webPath": "/listedco/listconews/sehk/2026/1028/suspend.pdf",
    "market": "SEHK",
    "stock": [{"sc": "01234", "sn": "測試停牌"}],
    "relTime": "28/10/2026 08:00",
    "t1Code": "10000",
    "t2Code": "17960",
}

NEXT_DAY_DISCLOSURE = {
    "newsId": 12380998,
    "title": "翌日披露報表",
    "lTxt": "翌日披露報表 - [股份購回]",
    "ext": "xls",
    "size": "10KB",
    "webPath": "/listedco/listconews/sehk/2026/1028/ndd.xls",
    "market": "SEHK",
    "stock": [{"sc": "00700", "sn": "騰訊控股"}],
    "relTime": "28/10/2026 08:00",
    "t1Code": "50000",
    "t2Code": "50100",
}

ESG_REPORT = {
    "newsId": 12380997,
    "title": "ESG 報告",
    "lTxt": "財務報表/環境、社會及管治資料 - [環境、社會及管治資料/報告]",
    "ext": "pdf",
    "size": "5MB",
    "webPath": "/listedco/listconews/sehk/2026/1028/esg.pdf",
    "market": "SEHK",
    "stock": [{"sc": "00700", "sn": "騰訊控股"}],
    "relTime": "28/10/2026 08:00",
    "t1Code": "40000",
    "t2Code": "40400",
}


@pytest.fixture
def gen(tmp_path, monkeypatch):
    monkeypatch.setenv("HKEX_DAYS", "36500")
    monkeypatch.setenv("HKEX_DOWNLOAD_PDF", "false")
    monkeypatch.setenv("HKEX_MAX_PAGES", "3")
    monkeypatch.setenv("HKEX_MAX_ITEMS", "50")
    monkeypatch.setenv("HKEX_REQUEST_INTERVAL", "0")
    monkeypatch.delenv("HKEX_T2_CODES", raising=False)
    monkeypatch.delenv("HKEX_KEYWORDS", raising=False)
    monkeypatch.delenv("HKEX_STOCKS", raising=False)
    return HkexFinancialReportsGenerator(base_dir=tmp_path)


def test_split_t2_codes_multi_value():
    assert split_t2_codes("13300,13250") == {"13300", "13250"}
    assert split_t2_codes("40100") == {"40100"}
    assert split_t2_codes("") == set()
    assert split_t2_codes(None) == set()


def test_normalize_stock_code_strips_leading_zeros():
    assert normalize_stock_code("00700") == "700"
    assert normalize_stock_code("700") == "700"
    assert normalize_stock_code("00005") == "5"
    assert normalize_stock_code("0") == "0"
    assert normalize_stock_code("") == ""


def test_parse_rel_time_hong_kong_to_utc():
    dt = parse_rel_time("28/10/2026 06:33")
    assert dt == datetime(2026, 10, 27, 22, 33, tzinfo=pytz.UTC)


def test_parse_rel_time_invalid_returns_none():
    assert parse_rel_time("not-a-date") is None
    assert parse_rel_time("") is None
    assert parse_rel_time(None) is None


def test_safe_filename_strips_illegal_chars_and_caps_length():
    name = safe_filename('a/b:c*d?"<>|e' + "x" * 80, max_len=50)
    assert "/" not in name
    assert ":" not in name
    assert "*" not in name
    assert len(name) <= 50


def test_default_t2_codes():
    assert DEFAULT_T2_CODES == {"40100", "40200", "30500", "30600", "30700"}


def test_parse_annual_report_fields(gen):
    article = gen._parse_item(ANNUAL_REPORT)
    assert article is not None
    assert article.url == HKEX_HOST + ANNUAL_REPORT["webPath"]
    assert article.title == "[騰訊控股] 2025 Annual Report"
    assert article.published_at == datetime(2026, 10, 27, 22, 33, tzinfo=pytz.UTC)
    assert article.summary == "2025 Annual Report"
    assert article.category == "港股财报"
    assert article.author == "HKEXnews"
    assert "00700" in article.content
    assert "騰訊控股" in article.content
    assert "年報" in article.content
    assert "pdf" in article.content
    assert "334KB" in article.content
    assert article.url in article.content


def test_parse_multi_stock_and_multi_t2(gen):
    article = gen._parse_item(MULTI_STOCK_HTM)
    assert article is not None
    assert article.title == "[美團－Ｗ、美團－ＷＲ] 全球發售"
    assert article.url.endswith("_c.htm")
    assert "03690" in article.content
    assert "83690" in article.content
    assert "htm" in article.content


def test_parse_missing_webpath_falls_back_to_newsid(gen):
    article = gen._parse_item(MISSING_WEBPATH)
    assert article is not None
    assert article.url == "https://www.hkexnews.hk/#newsId=12380004"


def test_default_filter_keeps_financial_reports(gen):
    assert gen._match_filters(ANNUAL_REPORT) is True
    assert gen._match_filters(MISSING_WEBPATH) is True
    assert gen._match_filters(PROSPECTUS) is True
    assert gen._match_filters(INTRODUCTION_LISTING) is True
    assert gen._match_filters(MULTI_STOCK_HTM) is True


def test_default_filter_excludes_results_and_non_financial(gen):
    assert gen._match_filters(QUARTERLY_RESULTS) is False
    assert gen._match_filters(SUSPENSION) is False
    assert gen._match_filters(NEXT_DAY_DISCLOSURE) is False
    assert gen._match_filters(ESG_REPORT) is False
    assert gen._parse_item(QUARTERLY_RESULTS) is None
    assert gen._parse_item(SUSPENSION) is None
    assert gen._parse_item(NEXT_DAY_DISCLOSURE) is None
    assert gen._parse_item(ESG_REPORT) is None


def test_custom_t2_codes_replace_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HKEX_T2_CODES", "40400")
    monkeypatch.setenv("HKEX_DAYS", "36500")
    monkeypatch.setenv("HKEX_DOWNLOAD_PDF", "false")
    monkeypatch.setenv("HKEX_REQUEST_INTERVAL", "0")
    custom = HkexFinancialReportsGenerator(base_dir=tmp_path)
    assert custom._match_filters(ESG_REPORT) is True
    assert custom._match_filters(ANNUAL_REPORT) is False


def test_stock_filter_matches_without_leading_zeros(tmp_path, monkeypatch):
    monkeypatch.setenv("HKEX_STOCKS", "700")
    monkeypatch.setenv("HKEX_DAYS", "36500")
    monkeypatch.setenv("HKEX_DOWNLOAD_PDF", "false")
    monkeypatch.setenv("HKEX_REQUEST_INTERVAL", "0")
    filtered = HkexFinancialReportsGenerator(base_dir=tmp_path)
    assert filtered._match_filters(ANNUAL_REPORT) is True
    assert filtered._match_filters(PROSPECTUS) is False


def test_keyword_filter_matches_title_or_ltxt(tmp_path, monkeypatch):
    monkeypatch.setenv("HKEX_KEYWORDS", "中期")
    monkeypatch.setenv("HKEX_DAYS", "36500")
    monkeypatch.setenv("HKEX_DOWNLOAD_PDF", "false")
    monkeypatch.setenv("HKEX_REQUEST_INTERVAL", "0")
    filtered = HkexFinancialReportsGenerator(base_dir=tmp_path)
    assert filtered._match_filters(MISSING_WEBPATH) is True
    assert filtered._match_filters(ANNUAL_REPORT) is False


def test_days_filter_drops_old_items(tmp_path, monkeypatch):
    monkeypatch.setenv("HKEX_DAYS", "7")
    monkeypatch.setenv("HKEX_DOWNLOAD_PDF", "false")
    monkeypatch.setenv("HKEX_REQUEST_INTERVAL", "0")
    filtered = HkexFinancialReportsGenerator(base_dir=tmp_path)
    now_hk = datetime.now(HK_TZ)
    old = dict(ANNUAL_REPORT)
    old["relTime"] = (now_hk - timedelta(days=10)).strftime("%d/%m/%Y %H:%M")
    recent = dict(ANNUAL_REPORT)
    recent["relTime"] = now_hk.strftime("%d/%m/%Y %H:%M")
    assert filtered._match_filters(old) is False
    assert filtered._match_filters(recent) is True


def test_invalid_rel_time_still_keeps_item(gen):
    item = dict(ANNUAL_REPORT)
    item["relTime"] = "bad"
    article = gen._parse_item(item)
    assert article is not None
    assert article.published_at.tzinfo is not None


def test_fetch_page_parses_json(gen):
    payload = {
        "genDate": 1793169772258,
        "maxNumOfFile": 5,
        "newsInfoLst": [ANNUAL_REPORT, QUARTERLY_RESULTS],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    with patch("generators.finance.hkex_financial_reports.requests.get", return_value=mock_resp) as mocked:
        items, max_file = gen._fetch_page(1)
    assert max_file == 5
    assert len(items) == 2
    mocked.assert_called_once()
    called_url = mocked.call_args[0][0]
    assert called_url.endswith("lcisehk7relsdc_1.json")


def test_fetch_page_http_error_returns_none(gen):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "oops"
    with patch("generators.finance.hkex_financial_reports.requests.get", return_value=mock_resp):
        items, max_file = gen._fetch_page(1)
    assert items is None
    assert max_file is None


def test_pagination_requests_until_max_file(gen):
    fillers = []
    for i in range(PAGE_CAPACITY - 2):
        filler = dict(SUSPENSION)
        filler["newsId"] = 20000000 + i
        filler["webPath"] = f"/listedco/listconews/sehk/2026/1028/suspend_{i}.pdf"
        fillers.append(filler)
    page1 = {
        "genDate": 1,
        "maxNumOfFile": 2,
        "newsInfoLst": [ANNUAL_REPORT, PROSPECTUS] + fillers,
    }
    page2 = {
        "genDate": 1,
        "maxNumOfFile": 2,
        "newsInfoLst": [MULTI_STOCK_HTM],
    }

    def fake_get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if url.endswith("_1.json"):
            resp.json.return_value = page1
        elif url.endswith("_2.json"):
            resp.json.return_value = page2
        else:
            resp.status_code = 404
            resp.json.side_effect = ValueError("not json")
        return resp

    with patch("generators.finance.hkex_financial_reports.requests.get", side_effect=fake_get) as mocked:
        articles = gen.fetch_articles()

    urls = [c[0][0] for c in mocked.call_args_list]
    assert len(urls) == 2
    assert urls[0].endswith("lcisehk7relsdc_1.json")
    assert urls[1].endswith("lcisehk7relsdc_2.json")
    assert len(articles) == 3


def test_pagination_stops_on_error_keeps_parsed(gen):
    page1 = {
        "genDate": 1,
        "maxNumOfFile": 2,
        "newsInfoLst": [ANNUAL_REPORT],
    }

    def fake_get(url, **kwargs):
        resp = MagicMock()
        if url.endswith("_1.json"):
            resp.status_code = 200
            resp.json.return_value = page1
        else:
            resp.status_code = 500
            resp.text = "fail"
        return resp

    with patch("generators.finance.hkex_financial_reports.requests.get", side_effect=fake_get):
        articles = gen.fetch_articles()
    assert len(articles) == 1
    assert articles[0].title.startswith("[騰訊控股]")


def test_run_max_articles_caps_fetch(gen):
    gen._run_max_articles = 1
    page1 = {
        "genDate": 1,
        "maxNumOfFile": 5,
        "newsInfoLst": [ANNUAL_REPORT, QUARTERLY_RESULTS, MULTI_STOCK_HTM],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = page1
    with patch("generators.finance.hkex_financial_reports.requests.get", return_value=mock_resp) as mocked:
        articles = gen.fetch_articles()
    assert len(articles) == 1
    assert mocked.call_count == 1


def test_max_items_stops_pagination(tmp_path, monkeypatch):
    monkeypatch.setenv("HKEX_DAYS", "36500")
    monkeypatch.setenv("HKEX_DOWNLOAD_PDF", "false")
    monkeypatch.setenv("HKEX_MAX_PAGES", "5")
    monkeypatch.setenv("HKEX_MAX_ITEMS", "1")
    monkeypatch.setenv("HKEX_REQUEST_INTERVAL", "0")
    limited = HkexFinancialReportsGenerator(base_dir=tmp_path)
    page1 = {
        "genDate": 1,
        "maxNumOfFile": 5,
        "newsInfoLst": [ANNUAL_REPORT, QUARTERLY_RESULTS],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = page1
    with patch("generators.finance.hkex_financial_reports.requests.get", return_value=mock_resp) as mocked:
        articles = limited.fetch_articles()
    assert len(articles) == 1
    assert mocked.call_count == 1


def test_duplicate_url_in_same_fetch_kept_once(gen):
    page1 = {
        "genDate": 1,
        "maxNumOfFile": 1,
        "newsInfoLst": [ANNUAL_REPORT, dict(ANNUAL_REPORT)],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = page1
    with patch("generators.finance.hkex_financial_reports.requests.get", return_value=mock_resp):
        articles = gen.fetch_articles()
    assert len(articles) == 1


def test_download_pdf_skipped_when_file_exists(gen, tmp_path):
    gen.download_pdf = True
    pdf_url = HKEX_HOST + ANNUAL_REPORT["webPath"]
    company_dir = tmp_path / "downloads" / "hkex_pdfs" / "騰訊控股_00700"
    company_dir.mkdir(parents=True)
    filename = "00700_" + safe_filename("2025 Annual Report") + ".pdf"
    existing = company_dir / filename
    existing.write_bytes(b"%PDF")
    with patch("generators.finance.hkex_financial_reports.requests.get") as mocked:
        path = gen._download_pdf(pdf_url, "00700", "2025 Annual Report", "騰訊控股")
    mocked.assert_not_called()
    assert path.endswith(filename)


def test_feed_metadata(gen):
    assert gen.FEED_NAME == "hkex_financial_reports"
    assert gen.FEED_TITLE == "披露易 - 港股财报"
    assert gen.FEED_LANGUAGE == "zh-HK"
    assert gen.FEED_URL == "https://www.hkexnews.hk/"
