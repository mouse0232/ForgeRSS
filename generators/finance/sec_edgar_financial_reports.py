#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SEC EDGAR annual report and prospectus RSS generator."""

import gzip
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

import pytz
import requests

from generators.base import Article, BaseFeedGenerator

NY_TZ = pytz.timezone("America/New_York")
ARCHIVES_BASE = "https://www.sec.gov/Archives/"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# SEC EDGAR 要求 UA 格式："<应用名> <联系邮箱>"
# SEC 会拉黑被识别为爬虫的 UA（含已知 app 名、noreply 邮箱、github.io 邮箱等）。
# 必须用真实的、非 noreply、非 github.io 的联系邮箱。
DEFAULT_USER_AGENT = "ForgeRSS admin@forgerss.dev"
FALLBACK_USER_AGENTS = [
    "ForgeRSS ops@forgerss.dev",
]
HEADER_NAMES = ("cik", "company name", "form type", "date filed")


logger = logging.getLogger(__name__)


def current_et_datetime() -> datetime:
    return datetime.now(NY_TZ)


def _parse_csv_env(name: str) -> List[str]:
    raw = os.getenv(name, "") or ""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() == "true"


def normalize_cik(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    stripped = text.lstrip("0")
    return stripped if stripped else "0"


def normalize_form_type(value: str) -> str:
    return (value or "").strip().upper()


def safe_filename(s: str, max_len: int = 50) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", (s or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).rstrip(". ")
    return cleaned[:max_len].rstrip(". ")


def quarter_for(day: date) -> int:
    return (day.month - 1) // 3 + 1


def master_idx_url(day: date, gzipped: bool = False) -> str:
    suffix = "idx.gz" if gzipped else "idx"
    return (
        "https://www.sec.gov/Archives/edgar/daily-index/"
        f"{day.year}/QTR{quarter_for(day)}/master.{day.strftime('%Y%m%d')}.{suffix}"
    )


def parse_date_filed(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        naive = datetime.strptime(str(value).strip(), "%Y%m%d")
        return NY_TZ.localize(naive).astimezone(pytz.UTC)
    except (ValueError, TypeError, pytz.exceptions.Error):
        return None


def format_filed_date(value: str) -> str:
    text = (value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def filing_urls(file_name: str) -> Optional[Dict[str, str]]:
    text = (file_name or "").strip().lstrip("/")
    if not text:
        return None
    parts = text.split("/")
    if len(parts) < 4 or parts[0] != "edgar" or parts[1] != "data":
        return None
    cik = parts[2]
    basename = parts[-1]
    if not basename:
        return None
    accession = basename.rsplit(".", 1)[0]
    if not accession:
        return None
    accession_nodash = accession.replace("-", "")
    return {
        "cik": cik,
        "accession": accession,
        "accession_nodash": accession_nodash,
        "txt_url": ARCHIVES_BASE + text,
        "index_url": (
            f"{ARCHIVES_BASE}edgar/data/{cik}/{accession_nodash}/"
            f"{accession}-index.htm"
        ),
        "file_name": text,
    }


def _is_header_line(line: str) -> bool:
    parts = [part.strip().lower() for part in line.split("|")]
    if len(parts) < 5:
        return False
    if tuple(parts[:4]) != HEADER_NAMES:
        return False
    return parts[4] in {"file name", "filename"}


def _is_separator_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) <= {"-"}


def _row_from_parts(parts: List[str]) -> Optional[dict]:
    if len(parts) != 5:
        return None
    cik, company, form_type, date_filed, file_name = [part.strip() for part in parts]
    if not cik or not form_type or not file_name:
        return None
    return {
        "cik": cik,
        "company": company,
        "form_type": form_type,
        "date_filed": date_filed,
        "file_name": file_name,
    }


def parse_master_idx(text: str) -> List[dict]:
    if not text:
        return []
    lines = text.splitlines()
    header_idx = None
    for index, line in enumerate(lines):
        if _is_header_line(line):
            header_idx = index
            break
    if header_idx is None:
        return _parse_fixed_width(lines)

    rows: List[dict] = []
    for line in lines[header_idx + 1 :]:
        if not line.strip() or _is_separator_line(line):
            continue
        parts = line.split("|")
        row = _row_from_parts(parts)
        if row is None:
            logger.warning("Skip malformed master.idx line: %s", line[:200])
            continue
        rows.append(row)
    return rows


def _parse_fixed_width_line(line: str) -> Optional[dict]:
    text = line.strip()
    if "edgar/" not in text or not text[:1].isdigit():
        return None
    try:
        left, file_tail = text.rsplit("edgar/", 1)
        file_name = "edgar/" + file_tail.strip()
        left, date_filed = left.strip().rsplit(None, 1)
        left, form_type = left.strip().rsplit(None, 1)
        cik, company = left.strip().split(None, 1)
    except ValueError:
        return None
    return _row_from_parts([cik, company, form_type, date_filed, file_name])


def _parse_fixed_width(lines: List[str]) -> List[dict]:
    rows: List[dict] = []
    for line in lines:
        row = _parse_fixed_width_line(line)
        if row:
            rows.append(row)
    return rows


def _decode_body(content: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


class IndexFetchError(RuntimeError):
    pass


class SecEdgarFinancialReportsGenerator(BaseFeedGenerator):
    """SEC EDGAR daily-index RSS generator for annual reports and prospectuses."""

    FEED_NAME = "sec_edgar_financial_reports"
    FEED_TITLE = "SEC EDGAR - US Annual Reports and Prospectuses"
    FEED_URL = "https://www.sec.gov/edgar/"
    FEED_DESCRIPTION = (
        "SEC EDGAR 上市公司年报（10-K/20-F）与招股文件（S-1/F-1/424B4）"
    )
    FEED_LANGUAGE = "en"

    def __init__(self, base_dir: Path = None):
        if os.getenv("SEC_FEED_NAME", "").strip():
            self.FEED_NAME = os.getenv("SEC_FEED_NAME").strip()
        if os.getenv("SEC_FEED_TITLE", "").strip():
            self.FEED_TITLE = os.getenv("SEC_FEED_TITLE").strip()
        if os.getenv("SEC_FEED_DESCRIPTION", "").strip():
            self.FEED_DESCRIPTION = os.getenv("SEC_FEED_DESCRIPTION").strip()

        super().__init__(base_dir=base_dir)

        forms_raw = _parse_csv_env("SEC_FORMS")
        base_forms = {normalize_form_type(item) for item in forms_raw}
        self.include_amendments = _env_bool("SEC_INCLUDE_AMENDMENTS", False)
        if self.include_amendments and base_forms:
            extras = {
                f"{form}/A"
                for form in base_forms
                if not form.endswith("/A")
            }
            self.forms = base_forms | extras
        else:
            self.forms = base_forms

        self.tickers = [item.upper() for item in _parse_csv_env("SEC_TICKERS")]
        self.ciks = {normalize_cik(item) for item in _parse_csv_env("SEC_CIKS")}
        self.ciks.discard("")
        self.keywords = _parse_csv_env("SEC_KEYWORDS")
        self.days = int(os.getenv("SEC_DAYS", "7"))
        self.max_items = int(os.getenv("SEC_MAX_ITEMS", "50"))
        self.max_index_days = int(os.getenv("SEC_MAX_INDEX_DAYS", "14"))
        self.request_interval = float(os.getenv("SEC_REQUEST_INTERVAL", "0.2"))
        self.download_txt = _env_bool("SEC_DOWNLOAD", False)
        self.user_agent = os.getenv("SEC_USER_AGENT", "").strip() or DEFAULT_USER_AGENT

        self.attachments_dir = self.base_dir / "downloads" / "sec_edgar"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
        self._ticker_ciks: Optional[Set[str]] = None
        self._last_request_at = 0.0
        self._allowed_ciks: Optional[Set[str]] = None
        self._allowed_ciks_ready = False

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    def _item_cap(self) -> int:
        cap = self.max_items
        run_cap = getattr(self, "_run_max_articles", None)
        if run_cap:
            cap = min(cap, int(run_cap))
        return cap

    def _iter_index_dates(self) -> Iterable[date]:
        today = current_et_datetime().date()
        start = today - timedelta(days=1)
        window = max(self.days, 1)
        limit = max(self.max_index_days, 1)
        count = min(window, limit)
        for offset in range(count):
            yield start - timedelta(days=offset)

    def fetch_articles(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: Set[str] = set()
        seen_accessions: Set[str] = set()
        cap = self._item_cap()
        got_index = False
        consecutive_misses = 0

        for day in self._iter_index_dates():
            if len(articles) >= cap:
                break
            try:
                text = self._fetch_master_idx(day)
            except IndexFetchError:
                break
            if text is None:
                consecutive_misses += 1
                if consecutive_misses >= self.max_index_days:
                    self.logger.error(
                        "No EDGAR daily index found after %s calendar days",
                        consecutive_misses,
                    )
                    break
                continue

            got_index = True
            consecutive_misses = 0
            rows = parse_master_idx(text)
            if not rows:
                self.logger.warning("Could not parse master.idx for %s", day.isoformat())
                continue

            for row in rows:
                article = self._parse_item(row)
                if article is None:
                    continue
                urls = filing_urls(row.get("file_name", ""))
                accession = (urls or {}).get("accession", "")
                if accession:
                    if accession in seen_accessions:
                        continue
                    seen_accessions.add(accession)
                if article.url in seen_urls:
                    continue
                seen_urls.add(article.url)
                articles.append(article)
                if len(articles) >= cap:
                    break

        if not got_index:
            self.logger.error("No EDGAR daily index found in the lookback window")
        return articles

    def _resolve_allowed_ciks(self) -> Optional[Set[str]]:
        if self._allowed_ciks_ready:
            return self._allowed_ciks
        ciks = set(self.ciks)
        if self.tickers:
            ciks |= self._load_ticker_ciks()
        self._allowed_ciks = ciks or None
        self._allowed_ciks_ready = True
        return self._allowed_ciks

    def _load_ticker_ciks(self) -> Set[str]:
        if self._ticker_ciks is not None:
            return self._ticker_ciks
        mapped: Set[str] = set()
        mapping: Dict[str, str] = {}
        try:
            response = self._request(TICKERS_URL)
            if response is None or response.status_code != 200:
                status = None if response is None else response.status_code
                self.logger.warning("Failed to load company_tickers.json: HTTP %s", status)
            else:
                payload = response.json()
                for item in payload.values():
                    ticker = str((item or {}).get("ticker") or "").upper()
                    cik = normalize_cik(str((item or {}).get("cik_str") or ""))
                    if ticker and cik:
                        mapping[ticker] = cik
        except Exception as exc:
            self.logger.warning("Failed to parse company_tickers.json: %s", exc)

        for ticker in self.tickers:
            cik = mapping.get(ticker.upper())
            if cik:
                mapped.add(cik)
            else:
                self.logger.warning("Unknown ticker %s; ignoring", ticker)
        self._ticker_ciks = mapped
        return mapped

    def _throttle(self) -> None:
        if self.request_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.request_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _request(
        self,
        url: str,
        timeout: int = 60,
        stream: bool = False,
    ) -> Optional[requests.Response]:
        backoff = 1.0
        last_error: Optional[Exception] = None
        for attempt in range(4):
            self._throttle()
            try:
                self._last_request_at = time.monotonic()
                response = requests.get(
                    url,
                    headers=self._headers(),
                    timeout=timeout,
                    stream=stream,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == 3:
                    self.logger.error("EDGAR request error for %s: %s", url, exc)
                    return None
                time.sleep(min(backoff, 600))
                backoff *= 2
                continue

            if response.status_code in (429, 503) and attempt < 3:
                self.logger.warning(
                    "EDGAR HTTP %s for %s, backing off %.1fs",
                    response.status_code,
                    url,
                    min(backoff, 600),
                )
                time.sleep(min(backoff, 600))
                backoff *= 2
                continue
            return response

        if last_error:
            self.logger.error("EDGAR request error for %s: %s", url, last_error)
        return None

    def _fetch_master_idx(self, day: date) -> Optional[str]:
        last_status = None
        for gzipped in (False, True):
            url = master_idx_url(day, gzipped=gzipped)
            response = self._request(url)
            if response is None:
                raise IndexFetchError(f"request failed for {url}")
            last_status = response.status_code
            if response.status_code == 404:
                continue
            if response.status_code == 403:
                self.logger.error(
                    "EDGAR request forbidden (HTTP 403) for %s. "
                    "Check SEC_USER_AGENT includes an app name and contact email.",
                    url,
                )
                raise IndexFetchError("HTTP 403")
            if response.status_code in (429, 503):
                self.logger.error(
                    "EDGAR rate-limited or unavailable (HTTP %s) for %s",
                    response.status_code,
                    url,
                )
                raise IndexFetchError(f"HTTP {response.status_code}")
            if response.status_code >= 500:
                self.logger.error(
                    "EDGAR request failed (HTTP %s) for %s",
                    response.status_code,
                    url,
                )
                raise IndexFetchError(f"HTTP {response.status_code}")
            if response.status_code != 200:
                self.logger.error(
                    "EDGAR request failed (HTTP %s) for %s",
                    response.status_code,
                    url,
                )
                raise IndexFetchError(f"HTTP {response.status_code}")
            body = response.content
            if gzipped:
                try:
                    body = gzip.decompress(body)
                except OSError:
                    pass
            return _decode_body(body)

        self.logger.info("No master.idx for %s (HTTP %s)", day.isoformat(), last_status)
        return None

    def _match_filters(self, row: dict) -> bool:
        form_type = normalize_form_type(row.get("form_type", ""))
        if self.forms and form_type not in self.forms:
            return False

        allowed = self._resolve_allowed_ciks()
        if allowed is not None:
            cik = normalize_cik(row.get("cik", ""))
            if cik not in allowed:
                return False

        if self.keywords:
            company = row.get("company") or ""
            haystack = company.lower()
            if not any(keyword.lower() in haystack for keyword in self.keywords):
                return False
        return True

    def _parse_item(self, row: dict) -> Optional[Article]:
        try:
            if not self._match_filters(row):
                return None

            urls = filing_urls(row.get("file_name", ""))
            if urls is None:
                self.logger.warning("Skip filing with empty or invalid File Name")
                return None

            company = (row.get("company") or "").strip()
            form_type = (row.get("form_type") or "").strip()
            date_filed = (row.get("date_filed") or "").strip()
            cik = (row.get("cik") or "").strip()
            filed_label = format_filed_date(date_filed)
            title = f"[{company}] {form_type} ({filed_label})"

            published_at = parse_date_filed(date_filed)
            if published_at is None:
                self.logger.warning(
                    "Unparseable Date Filed %r for accession=%s",
                    date_filed,
                    urls["accession"],
                )
                published_at = datetime.now(pytz.UTC)

            local_path = None
            if self.download_txt:
                local_path = self._download_filing(
                    urls["txt_url"],
                    company,
                    cik,
                    form_type,
                    date_filed,
                    urls["accession"],
                )

            content_parts = [
                f"<h3>{title}</h3>",
                f"<p><strong>Company:</strong> {company}</p>",
                f"<p><strong>CIK:</strong> {cik}</p>",
                f"<p><strong>Form Type:</strong> {form_type}</p>",
                f"<p><strong>Date Filed:</strong> {filed_label}</p>",
                f"<p><strong>Accession Number:</strong> {urls['accession']}</p>",
                (
                    f'<p><strong>Index:</strong> '
                    f'<a href="{urls["index_url"]}">{urls["index_url"]}</a></p>'
                ),
                (
                    f'<p><strong>Complete submission:</strong> '
                    f'<a href="{urls["txt_url"]}">{urls["txt_url"]}</a></p>'
                ),
            ]
            if local_path:
                content_parts.append(
                    f"<p><strong>Local path:</strong> <code>{local_path}</code></p>"
                )

            return Article(
                url=urls["index_url"],
                title=title,
                published_at=published_at,
                content="\n".join(content_parts),
                summary=title[:200],
                category="美股财报",
                author="SEC EDGAR",
            )
        except Exception as exc:
            self.logger.warning("Error parsing EDGAR item: %s", exc)
            return None

    def _download_filing(
        self,
        txt_url: str,
        company: str,
        cik: str,
        form_type: str,
        date_filed: str,
        accession: str,
    ) -> Optional[str]:
        try:
            safe_company = safe_filename(company, max_len=30)
            company_dir_name = f"{safe_company}_{cik}" if safe_company else cik
            company_dir = self.attachments_dir / company_dir_name
            company_dir.mkdir(parents=True, exist_ok=True)
            filename = safe_filename(
                f"{form_type}_{date_filed}_{accession}",
                max_len=80,
            )
            if not filename.lower().endswith(".txt"):
                filename = f"{filename}.txt"
            file_path = company_dir / filename

            if file_path.exists():
                try:
                    return str(file_path.relative_to(self.base_dir))
                except ValueError:
                    return str(file_path)

            response = self._request(txt_url, timeout=60, stream=True)
            if response is None or response.status_code != 200:
                status = None if response is None else response.status_code
                self.logger.warning("Filing download failed: %s %s", status, txt_url)
                return None

            with open(file_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    handle.write(chunk)

            self.logger.info(
                "Downloaded: %s (%.1f KB)",
                filename,
                file_path.stat().st_size / 1024,
            )
            try:
                return str(file_path.relative_to(self.base_dir))
            except ValueError:
                return str(file_path)
        except Exception as exc:
            self.logger.error("Error downloading filing: %s", exc)
            return None


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="SEC EDGAR annual reports and prospectuses RSS"
    )
    parser.add_argument("--forms", help="Form types, comma-separated (e.g. 10-K,20-F)")
    parser.add_argument("--tickers", help="Tickers, comma-separated (e.g. AAPL,MSFT)")
    parser.add_argument("--ciks", help="CIKs, comma-separated")
    parser.add_argument("--keywords", help="Company-name keywords, comma-separated")
    parser.add_argument("--days", type=int, default=None, help="Closed ET lookback days")
    parser.add_argument("--max", type=int, default=50, help="Max feed items")
    parser.add_argument(
        "--include-amendments",
        action="store_true",
        help="Also keep /A amendments",
    )
    parser.add_argument("--download", action="store_true", help="Download complete .txt")
    parser.add_argument("--feed-name", help="Output feed name")
    parser.add_argument("--feed-title", help="RSS channel title")
    parser.add_argument("--full", action="store_true", help="Full refresh (ignore cache)")
    args = parser.parse_args()

    if args.forms:
        os.environ["SEC_FORMS"] = args.forms
    if args.tickers:
        os.environ["SEC_TICKERS"] = args.tickers
    if args.ciks:
        os.environ["SEC_CIKS"] = args.ciks
    if args.keywords:
        os.environ["SEC_KEYWORDS"] = args.keywords
    if args.days is not None:
        os.environ["SEC_DAYS"] = str(args.days)
    os.environ["SEC_MAX_ITEMS"] = str(args.max)
    os.environ["SEC_INCLUDE_AMENDMENTS"] = "true" if args.include_amendments else "false"
    os.environ["SEC_DOWNLOAD"] = "true" if args.download else "false"
    if args.feed_name:
        os.environ["SEC_FEED_NAME"] = args.feed_name
    if args.feed_title:
        os.environ["SEC_FEED_TITLE"] = args.feed_title

    generator = SecEdgarFinancialReportsGenerator()
    result = generator.run(full_refresh=args.full, max_articles=args.max)
    if result:
        print("\n[OK] 成功生成RSS feed")
    else:
        print("\n[ERROR] 生成失败")


if __name__ == "__main__":
    main()
