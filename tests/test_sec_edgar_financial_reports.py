#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytz
import pytest

from generators.finance.sec_edgar_financial_reports import (
    DEFAULT_USER_AGENT,
    NY_TZ,
    IndexFetchError,
    SecEdgarFinancialReportsGenerator,
    filing_urls,
    format_filed_date,
    master_idx_url,
    normalize_cik,
    normalize_form_type,
    parse_date_filed,
    parse_master_idx,
    quarter_for,
    safe_filename,
)

MASTER_IDX_FIXTURE = """Description:           Daily Index of EDGAR Dissemination Feed
Last Data Received:    Oct 28, 2026
Comments:              webmaster@sec.gov
Anonymous FTP:         ftp://ftp.sec.gov/edgar/

CIK|Company Name|Form Type|Date Filed|File Name
--------------------------------------------------------------------------------
1000275|ROYAL BANK OF CANADA|424B2|20261028|edgar/data/1000275/0000950103-26-016266.txt
1610820|BriaCell Therapeutics Corp.|10-K|20261028|edgar/data/1610820/0001493152-26-049041.txt
2123920|Focus Media Network Ltd|F-1|20261028|edgar/data/2123920/0001213900-26-113189.txt
717954|UNIFIRST CORP|10-K|20261028|edgar/data/717954/0001628280-26-067689.txt
320193|Apple Inc.|8-K|20261028|edgar/data/320193/0000320193-26-000111.txt
320193|Apple Inc.|10-Q|20261028|edgar/data/320193/0000320193-26-000112.txt
1956741|Zone Frontier Inc.|10-K/A|20261028|edgar/data/1956741/0001213900-26-113383.txt
1111111|Example Issuer Inc.|S-1/A|20261028|edgar/data/1111111/0001111111-26-000001.txt
1234567|UNIVERSAL DISPLAY CORP \\PA\\|10-K|20261028|edgar/data/1234567/0001234567-26-000099.txt
1610820|BriaCell Therapeutics Corp.|10-K|20261028|edgar/data/1610820/0001493152-26-049041.txt
"""

FIXED_WIDTH_FIXTURE = """Description:           Daily Index of EDGAR Dissemination Feed

CIK   Company Name                              Form Type   Date Filed  File Name
--------------------------------------------------------------------------------
1610820   BriaCell Therapeutics Corp.           10-K        20261028    edgar/data/1610820/0001493152-26-049041.txt
"""

TEN_K = {
    "cik": "1610820",
    "company": "BriaCell Therapeutics Corp.",
    "form_type": "10-K",
    "date_filed": "20261028",
    "file_name": "edgar/data/1610820/0001493152-26-049041.txt",
}
F1 = {
    "cik": "2123920",
    "company": "Focus Media Network Ltd",
    "form_type": "F-1",
    "date_filed": "20261028",
    "file_name": "edgar/data/2123920/0001213900-26-113189.txt",
}
EIGHT_K = {
    "cik": "320193",
    "company": "Apple Inc.",
    "form_type": "8-K",
    "date_filed": "20261028",
    "file_name": "edgar/data/320193/0000320193-26-000111.txt",
}
TEN_Q = {
    "cik": "320193",
    "company": "Apple Inc.",
    "form_type": "10-Q",
    "date_filed": "20261028",
    "file_name": "edgar/data/320193/0000320193-26-000112.txt",
}
B424B2 = {
    "cik": "1000275",
    "company": "ROYAL BANK OF CANADA",
    "form_type": "424B2",
    "date_filed": "20261028",
    "file_name": "edgar/data/1000275/0000950103-26-016266.txt",
}
TEN_K_A = {
    "cik": "1956741",
    "company": "Zone Frontier Inc.",
    "form_type": "10-K/A",
    "date_filed": "20261028",
    "file_name": "edgar/data/1956741/0001213900-26-113383.txt",
}
S1_A = {
    "cik": "1111111",
    "company": "Example Issuer Inc.",
    "form_type": "S-1/A",
    "date_filed": "20261028",
    "file_name": "edgar/data/1111111/0001111111-26-000001.txt",
}
APPLE_10K = {
    "cik": "320193",
    "company": "Apple Inc.",
    "form_type": "10-K",
    "date_filed": "20261028",
    "file_name": "edgar/data/320193/0000320193-24-000123.txt",
}
BACKSLASH_NAME = {
    "cik": "1234567",
    "company": "UNIVERSAL DISPLAY CORP \\PA\\",
    "form_type": "10-K",
    "date_filed": "20261028",
    "file_name": "edgar/data/1234567/0001234567-26-000099.txt",
}


@pytest.fixture
def gen(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_DAYS", "7")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    monkeypatch.setenv("SEC_MAX_ITEMS", "50")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_INCLUDE_AMENDMENTS", "false")
    monkeypatch.delenv("SEC_FORMS", raising=False)
    monkeypatch.delenv("SEC_TICKERS", raising=False)
    monkeypatch.delenv("SEC_CIKS", raising=False)
    monkeypatch.delenv("SEC_KEYWORDS", raising=False)
    monkeypatch.delenv("SEC_FEED_NAME", raising=False)
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("SEC_FEED_TITLE", raising=False)
    monkeypatch.delenv("SEC_FEED_DESCRIPTION", raising=False)
    return SecEdgarFinancialReportsGenerator(base_dir=tmp_path)


def test_normalize_cik_strips_leading_zeros():
    assert normalize_cik("0000320193") == "320193"
    assert normalize_cik("320193") == "320193"
    assert normalize_cik("0") == "0"
    assert normalize_cik("") == ""


def test_normalize_form_type_uppercases():
    assert normalize_form_type("10-k") == "10-K"
    assert normalize_form_type(" s-1/a ") == "S-1/A"


def test_quarter_and_master_url():
    assert quarter_for(date(2026, 10, 28)) == 4
    assert quarter_for(date(2026, 1, 2)) == 1
    url = master_idx_url(date(2026, 10, 28))
    assert url == (
        "https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.20261028.idx"
    )
    gz = master_idx_url(date(2026, 10, 28), gzipped=True)
    assert gz.endswith("master.20261028.idx.gz")


def test_parse_master_idx_splits_pipe_rows():
    rows = parse_master_idx(MASTER_IDX_FIXTURE)
    assert len(rows) == 10
    first = rows[0]
    assert first["cik"] == "1000275"
    assert first["company"] == "ROYAL BANK OF CANADA"
    assert first["form_type"] == "424B2"
    assert first["date_filed"] == "20261028"
    ten_k = [row for row in rows if row["form_type"] == "10-K"]
    assert ten_k[0]["cik"] == "1610820"
    slash = [row for row in rows if "UNIVERSAL DISPLAY" in row["company"]][0]
    assert slash["company"] == "UNIVERSAL DISPLAY CORP \\PA\\"
    assert slash["cik"] == "1234567"


def test_parse_master_idx_skips_bad_lines():
    text = MASTER_IDX_FIXTURE + "not-enough-fields\n1|2|3|4\n"
    rows = parse_master_idx(text)
    assert len(rows) == 10


def test_parse_master_idx_fixed_width_fallback():
    rows = parse_master_idx(FIXED_WIDTH_FIXTURE)
    assert len(rows) == 1
    assert rows[0]["form_type"] == "10-K"
    assert rows[0]["cik"] == "1610820"
    assert rows[0]["file_name"].endswith("0001493152-26-049041.txt")


def test_filing_urls_from_file_name():
    urls = filing_urls("edgar/data/1610820/0001493152-26-049041.txt")
    assert urls["cik"] == "1610820"
    assert urls["accession"] == "0001493152-26-049041"
    assert urls["accession_nodash"] == "000149315226049041"
    assert urls["txt_url"] == (
        "https://www.sec.gov/Archives/edgar/data/1610820/0001493152-26-049041.txt"
    )
    assert urls["index_url"] == (
        "https://www.sec.gov/Archives/edgar/data/1610820/"
        "000149315226049041/0001493152-26-049041-index.htm"
    )


def test_filing_urls_apple_example():
    urls = filing_urls("edgar/data/320193/0000320193-24-000123.txt")
    assert urls["index_url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019324000123/0000320193-24-000123-index.htm"
    )


def test_parse_date_filed_et_to_utc():
    dt = parse_date_filed("20261028")
    assert dt == datetime(2026, 10, 28, 4, 0, tzinfo=pytz.UTC)
    assert format_filed_date("20261028") == "2026-10-28"


def test_parse_date_filed_invalid_returns_none():
    assert parse_date_filed("not-a-date") is None
    assert parse_date_filed("") is None
    assert parse_date_filed(None) is None


def test_safe_filename_strips_illegal_chars_and_caps_length():
    name = safe_filename('a/b:c*d?"<>|e' + "x" * 80, max_len=50)
    assert "/" not in name
    assert ":" not in name
    assert "*" not in name
    assert len(name) <= 50


def test_unset_sec_forms_keeps_all_form_types(gen):
    assert gen.forms == set()
    assert gen._match_filters(TEN_K) is True
    assert gen._match_filters(F1) is True
    assert gen._match_filters(APPLE_10K) is True
    assert gen._match_filters(EIGHT_K) is True
    assert gen._match_filters(TEN_Q) is True
    assert gen._match_filters(B424B2) is True
    assert gen._match_filters(TEN_K_A) is True
    assert gen._match_filters(S1_A) is True


def test_workflow_forms_keep_10k_20f_424b4(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_FORMS", "10-K,20-F,424B4")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    assert custom._match_filters(TEN_K) is True
    assert custom._match_filters(F1) is False
    assert custom._match_filters(EIGHT_K) is False
    assert custom._match_filters(TEN_Q) is False
    assert custom._match_filters(B424B2) is False
    assert custom._parse_item(EIGHT_K) is None
    assert custom._parse_item(B424B2) is None


def test_include_amendments_keeps_slash_a(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_FORMS", "10-K,20-F,S-1,F-1,424B4")
    monkeypatch.setenv("SEC_INCLUDE_AMENDMENTS", "true")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    assert "10-K/A" in custom.forms
    assert "S-1/A" in custom.forms
    assert custom._match_filters(TEN_K_A) is True
    assert custom._match_filters(S1_A) is True
    assert custom._match_filters(TEN_K) is True
    assert custom._match_filters(EIGHT_K) is False


def test_custom_forms_replace_default(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_FORMS", "8-K")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    assert custom._match_filters(EIGHT_K) is True
    assert custom._match_filters(TEN_K) is False


def test_cik_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_CIKS", "0000320193")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    assert custom._match_filters(APPLE_10K) is True
    assert custom._match_filters(TEN_K) is False


def test_keyword_filter_matches_company_name(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_KEYWORDS", "briacell")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    assert custom._match_filters(TEN_K) is True
    assert custom._match_filters(F1) is False


def test_ticker_filter_maps_via_company_tickers(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_TICKERS", "AAPL")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}
    }
    with patch.object(custom, "_request", return_value=mock_resp):
        assert custom._match_filters(APPLE_10K) is True
        assert custom._match_filters(TEN_K) is False


def test_parse_item_fields(gen):
    article = gen._parse_item(TEN_K)
    assert article is not None
    assert article.title == "[BriaCell Therapeutics Corp.] 10-K (2026-10-28)"
    assert article.url == (
        "https://www.sec.gov/Archives/edgar/data/1610820/"
        "000149315226049041/0001493152-26-049041-index.htm"
    )
    assert article.published_at == datetime(2026, 10, 28, 4, 0, tzinfo=pytz.UTC)
    assert article.summary == article.title
    assert article.category == "美股财报"
    assert article.author == "SEC EDGAR"
    assert "1610820" in article.content
    assert "10-K" in article.content
    assert "0001493152-26-049041" in article.content
    assert article.url in article.content
    assert "0001493152-26-049041.txt" in article.content


def test_parse_item_backslash_company(gen):
    article = gen._parse_item(BACKSLASH_NAME)
    assert article is not None
    assert "UNIVERSAL DISPLAY CORP \\PA\\" in article.title


def test_invalid_date_filed_still_keeps_item(gen):
    item = dict(TEN_K)
    item["date_filed"] = "bad"
    article = gen._parse_item(item)
    assert article is not None
    assert article.published_at.tzinfo is not None


def test_iter_index_dates_t_plus_one_excludes_today(gen):
    frozen = NY_TZ.localize(datetime(2026, 10, 29, 15, 30))
    with patch(
        "generators.finance.sec_edgar_financial_reports.current_et_datetime",
        return_value=frozen,
    ):
        days = list(gen._iter_index_dates())
    assert days[0] == date(2026, 10, 28)
    assert date(2026, 10, 29) not in days
    assert len(days) == 7


def test_fetch_skips_404_weekend_and_stops_on_error(gen):
    frozen = NY_TZ.localize(datetime(2026, 11, 2, 9, 0))
    requested = []

    def fake_fetch(day):
        requested.append(day)
        if day == date(2026, 11, 1) or day == date(2026, 10, 31):
            return None
        if day == date(2026, 10, 30):
            return MASTER_IDX_FIXTURE
        raise IndexFetchError("HTTP 500")

    with patch(
        "generators.finance.sec_edgar_financial_reports.current_et_datetime",
        return_value=frozen,
    ), patch.object(gen, "_fetch_master_idx", side_effect=fake_fetch):
        articles = gen.fetch_articles()

    assert requested[0] == date(2026, 11, 1)
    assert date(2026, 11, 2) not in requested
    assert date(2026, 10, 31) in requested
    assert date(2026, 10, 30) in requested
    urls = [article.url for article in articles]
    assert len(urls) == len(set(urls))
    forms = {article.title.split("] ", 1)[1].split(" ", 1)[0] for article in articles}
    assert "10-K" in forms
    assert "F-1" in forms
    assert "8-K" in forms
    assert "424B2" in forms


def test_accession_dedup_in_fetch(gen):
    frozen = NY_TZ.localize(datetime(2026, 10, 29, 8, 0))
    with patch(
        "generators.finance.sec_edgar_financial_reports.current_et_datetime",
        return_value=frozen,
    ), patch.object(gen, "_fetch_master_idx", return_value=MASTER_IDX_FIXTURE):
        articles = gen.fetch_articles()
    briacell = [
        article for article in articles if "BriaCell" in article.title
    ]
    assert len(briacell) == 1


def test_max_items_stops_lookback(gen):
    gen.max_items = 1
    frozen = NY_TZ.localize(datetime(2026, 10, 29, 8, 0))
    calls = []

    def fake_fetch(day):
        calls.append(day)
        return MASTER_IDX_FIXTURE

    with patch(
        "generators.finance.sec_edgar_financial_reports.current_et_datetime",
        return_value=frozen,
    ), patch.object(gen, "_fetch_master_idx", side_effect=fake_fetch):
        articles = gen.fetch_articles()
    assert len(articles) == 1
    assert len(calls) == 1


def test_fetch_master_idx_404_then_gzip(gen):
    miss = MagicMock()
    miss.status_code = 404
    hit = MagicMock()
    hit.status_code = 200
    hit.content = MASTER_IDX_FIXTURE.encode("utf-8")
    with patch.object(gen, "_request", side_effect=[miss, hit]) as mocked:
        text = gen._fetch_master_idx(date(2026, 10, 28))
    assert "BriaCell" in text
    urls = [call.args[0] for call in mocked.call_args_list]
    assert urls[0].endswith("master.20261028.idx")
    assert urls[1].endswith("master.20261028.idx.gz")


def test_fetch_master_idx_404_both_returns_none(gen):
    miss = MagicMock()
    miss.status_code = 404
    with patch.object(gen, "_request", return_value=miss):
        assert gen._fetch_master_idx(date(2026, 10, 25)) is None


def test_fetch_master_idx_403_raises(gen):
    forbidden = MagicMock()
    forbidden.status_code = 403
    with patch.object(gen, "_request", return_value=forbidden):
        with pytest.raises(IndexFetchError):
            gen._fetch_master_idx(date(2026, 10, 28))


def test_user_agent_default(gen):
    assert gen.user_agent == DEFAULT_USER_AGENT
    headers = gen._headers()
    assert "ForgeRSS" in headers["User-Agent"]
    assert "@" in headers["User-Agent"]


def test_download_skips_existing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_DOWNLOAD", "true")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    existing = (
        custom.attachments_dir
        / "BriaCell Therapeutics Corp_1610820"
        / "10-K_20261028_0001493152-26-049041.txt"
    )
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("already here")
    with patch.object(custom, "_request") as mocked:
        path = custom._download_filing(
            "https://www.sec.gov/Archives/edgar/data/1610820/0001493152-26-049041.txt",
            "BriaCell Therapeutics Corp.",
            "1610820",
            "10-K",
            "20261028",
            "0001493152-26-049041",
        )
    mocked.assert_not_called()
    assert path.endswith("10-K_20261028_0001493152-26-049041.txt")
    article = custom._parse_item(TEN_K)
    assert "Local path" in article.content


def test_feed_name_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_FEED_NAME", "sec_edgar_ipo")
    monkeypatch.setenv("SEC_REQUEST_INTERVAL", "0")
    monkeypatch.setenv("SEC_DOWNLOAD", "false")
    custom = SecEdgarFinancialReportsGenerator(base_dir=tmp_path)
    assert custom.FEED_NAME == "sec_edgar_ipo"
