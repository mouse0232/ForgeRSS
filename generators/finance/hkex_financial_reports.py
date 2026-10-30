#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HKEXnews financial reports RSS generator."""

import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Set, Tuple

import pytz
import requests

from generators.base import Article, BaseFeedGenerator

HKEX_HOST = "https://www1.hkexnews.hk"
JSON_URL_TEMPLATE = (
    "https://www1.hkexnews.hk/ncms/json/eds/lcisehk7relsdc_{page}.json"
)
FALLBACK_URL_TEMPLATE = "https://www.hkexnews.hk/#newsId={news_id}"
HK_TZ = pytz.timezone("Asia/Hong_Kong")

DEFAULT_T2_CODES = {"40100", "40200", "30500", "30600", "30700"}
PAGE_CAPACITY = 500

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www1.hkexnews.hk/listedco/listconews/index/lci.html",
    "Accept": "application/json",
}


def split_t2_codes(value) -> Set[str]:
    if not value:
        return set()
    return {part.strip() for part in str(value).split(",") if part.strip()}


def normalize_stock_code(code: str) -> str:
    text = (code or "").strip()
    if not text:
        return ""
    stripped = text.lstrip("0")
    return stripped if stripped else "0"


def parse_rel_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        naive = datetime.strptime(str(value).strip(), "%d/%m/%Y %H:%M")
        localized = HK_TZ.localize(naive)
        return localized.astimezone(pytz.UTC)
    except (ValueError, TypeError, pytz.exceptions.Error):
        return None


def safe_filename(s: str, max_len: int = 50) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", (s or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).rstrip(". ")
    return cleaned[:max_len].rstrip(". ")


def _parse_csv_env(name: str) -> List[str]:
    raw = os.getenv(name, "") or ""
    return [part.strip() for part in raw.split(",") if part.strip()]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() == "true"


class HkexFinancialReportsGenerator(BaseFeedGenerator):
    """HKEXnews listed-company financial reports RSS generator."""

    FEED_NAME = "hkex_financial_reports"
    FEED_TITLE = "披露易 - 港股财报"
    FEED_URL = "https://www.hkexnews.hk/"
    FEED_DESCRIPTION = "港交所披露易上市公司年报、中期报告与招股/上市文件"
    FEED_LANGUAGE = "zh-HK"

    def __init__(self, base_dir: Path = None):
        if os.getenv("HKEX_FEED_NAME", "").strip():
            self.FEED_NAME = os.getenv("HKEX_FEED_NAME").strip()
        if os.getenv("HKEX_FEED_TITLE", "").strip():
            self.FEED_TITLE = os.getenv("HKEX_FEED_TITLE").strip()
        if os.getenv("HKEX_FEED_DESCRIPTION", "").strip():
            self.FEED_DESCRIPTION = os.getenv("HKEX_FEED_DESCRIPTION").strip()

        super().__init__(base_dir=base_dir)

        t1_raw = _parse_csv_env("HKEX_T1_CODES")
        t2_raw = _parse_csv_env("HKEX_T2_CODES")
        if t1_raw or t2_raw:
            self.t1_codes = set(t1_raw)
            self.t2_codes = set(t2_raw)
        else:
            self.t1_codes = set()
            self.t2_codes = set(DEFAULT_T2_CODES)
        self.keywords = _parse_csv_env("HKEX_KEYWORDS")
        self.stocks = {normalize_stock_code(code) for code in _parse_csv_env("HKEX_STOCKS")}
        self.stocks.discard("")
        self.days = int(os.getenv("HKEX_DAYS", "7"))
        self.max_items = int(os.getenv("HKEX_MAX_ITEMS", "50"))
        self.max_pages = int(os.getenv("HKEX_MAX_PAGES", "1"))
        self.request_interval = float(os.getenv("HKEX_REQUEST_INTERVAL", "1.0"))
        self.download_pdf = _env_bool("HKEX_DOWNLOAD_PDF", False)

        self.attachments_dir = self.base_dir / "downloads" / "hkex_pdfs"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)

    def _item_cap(self) -> int:
        cap = self.max_items
        run_cap = getattr(self, "_run_max_articles", None)
        if run_cap:
            cap = min(cap, int(run_cap))
        return cap

    def fetch_articles(self) -> List[Article]:
        articles: List[Article] = []
        seen_urls: Set[str] = set()
        max_num_of_file = 1
        page = 1
        cap = self._item_cap()

        while (
            len(articles) < cap
            and page <= self.max_pages
            and page <= max_num_of_file
        ):
            if page > 1 and self.request_interval > 0:
                time.sleep(self.request_interval)

            items, page_max = self._fetch_page(page)
            if items is None:
                break
            if page_max:
                max_num_of_file = int(page_max)
            if not items:
                break

            for item in items:
                article = self._parse_item(item)
                if article is None:
                    continue
                if article.url in seen_urls:
                    continue
                seen_urls.add(article.url)
                articles.append(article)
                if len(articles) >= cap:
                    break

            if len(items) < PAGE_CAPACITY:
                break
            page += 1

        return articles

    def _fetch_page(self, page: int) -> Tuple[Optional[List[dict]], Optional[int]]:
        url = JSON_URL_TEMPLATE.format(page=page)
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
            if response.status_code != 200:
                self.logger.error(
                    "HKEXnews JSON request failed: %s %s",
                    response.status_code,
                    url,
                )
                return None, None
            data = response.json()
        except Exception as exc:
            self.logger.error("HKEXnews JSON error on page %s: %s", page, exc)
            return None, None

        items = data.get("newsInfoLst") or []
        max_num = data.get("maxNumOfFile") or 1
        self.logger.info(
            "Fetched %s items from HKEXnews page %s (maxNumOfFile=%s)",
            len(items),
            page,
            max_num,
        )
        return items, max_num

    def _match_filters(self, item: dict) -> bool:
        item_t1 = split_t2_codes(item.get("t1Code"))
        item_t2 = split_t2_codes(item.get("t2Code"))
        if self.t1_codes and not (item_t1 & self.t1_codes):
            return False
        if self.t2_codes and not (item_t2 & self.t2_codes):
            return False

        if self.keywords:
            haystack = f"{item.get('title') or ''} {item.get('lTxt') or ''}"
            if not any(keyword in haystack for keyword in self.keywords):
                return False

        if self.stocks:
            stock_codes = {
                normalize_stock_code((stock or {}).get("sc", ""))
                for stock in (item.get("stock") or [])
            }
            if not (stock_codes & self.stocks):
                return False

        if self.days > 0:
            published = parse_rel_time(item.get("relTime"))
            if published is not None:
                cutoff_date = (
                    datetime.now(HK_TZ).date() - timedelta(days=self.days)
                )
                if published.astimezone(HK_TZ).date() < cutoff_date:
                    return False

        return True

    def _parse_item(self, item: dict) -> Optional[Article]:
        try:
            if not self._match_filters(item):
                return None

            news_id = item.get("newsId")
            title = (item.get("title") or "").strip()
            if not title and not news_id:
                self.logger.warning("Skip item with missing title and newsId")
                return None

            stocks = item.get("stock") or []
            names = [
                (stock or {}).get("sn", "").strip()
                for stock in stocks
                if (stock or {}).get("sn")
            ]
            codes = [
                (stock or {}).get("sc", "").strip()
                for stock in stocks
                if (stock or {}).get("sc")
            ]
            name_label = "、".join(names)
            display_title = f"[{name_label}] {title}" if name_label else title

            web_path = (item.get("webPath") or "").strip()
            if web_path:
                url = HKEX_HOST + web_path
            elif news_id is not None:
                url = FALLBACK_URL_TEMPLATE.format(news_id=news_id)
            else:
                self.logger.warning("Skip item with empty webPath and newsId")
                return None

            published_at = parse_rel_time(item.get("relTime"))
            if published_at is None:
                self.logger.warning(
                    "Unparseable relTime %r for newsId=%s",
                    item.get("relTime"),
                    news_id,
                )
                published_at = datetime.now(pytz.UTC)

            local_pdf_path = None
            ext = (item.get("ext") or "").strip().lower()
            if self.download_pdf and ext == "pdf" and web_path:
                primary_code = codes[0] if codes else str(news_id or "unknown")
                primary_name = names[0] if names else ""
                local_pdf_path = self._download_pdf(
                    url, primary_code, title, primary_name
                )

            time_text = published_at.astimezone(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")
            content_parts = [
                f"<h3>{display_title}</h3>",
                f"<p><strong>股票代码:</strong> {'、'.join(codes)}</p>",
                f"<p><strong>股票简称:</strong> {name_label}</p>",
                f"<p><strong>披露类别:</strong> {item.get('lTxt') or ''}</p>",
                f"<p><strong>发布时间:</strong> {time_text}</p>",
                f"<p><strong>文件类型:</strong> {item.get('ext') or ''}</p>",
                f"<p><strong>文件大小:</strong> {item.get('size') or ''}</p>",
                f'<p><strong>原文链接:</strong> <a href="{url}">查看原文</a></p>',
            ]
            if local_pdf_path:
                content_parts.append(
                    f"<p><strong>本地路径:</strong> <code>{local_pdf_path}</code></p>"
                )

            return Article(
                url=url,
                title=display_title,
                published_at=published_at,
                content="\n".join(content_parts),
                summary=(title or display_title)[:200],
                category="港股财报",
                author="HKEXnews",
            )
        except Exception as exc:
            self.logger.warning("Error parsing HKEXnews item: %s", exc)
            return None

    def _download_pdf(
        self,
        pdf_url: str,
        sec_code: str,
        title: str,
        sec_name: str = "",
    ) -> Optional[str]:
        try:
            safe_title = safe_filename(title)
            filename = f"{sec_code}_{safe_title}.pdf"
            safe_name = safe_filename(sec_name, max_len=30)
            company_dir_name = f"{safe_name}_{sec_code}" if safe_name else sec_code
            company_dir = self.attachments_dir / company_dir_name
            company_dir.mkdir(parents=True, exist_ok=True)
            file_path = company_dir / filename

            if file_path.exists():
                try:
                    return str(file_path.relative_to(self.base_dir))
                except ValueError:
                    return str(file_path)

            response = requests.get(
                pdf_url, headers=REQUEST_HEADERS, stream=True, timeout=60
            )
            if response.status_code != 200:
                self.logger.warning(
                    "PDF download failed: %s %s", response.status_code, pdf_url
                )
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
            self.logger.error("Error downloading PDF: %s", exc)
            return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="HKEXnews financial reports RSS")
    parser.add_argument("--stocks", help="股份代号，逗号分隔（如 700,941）")
    parser.add_argument("--keywords", help="标题/类别关键词，逗号分隔")
    parser.add_argument("--t1-codes", help="一级标题代码，逗号分隔（如 40000,30000）")
    parser.add_argument("--t2-codes", help="二级标题代码，逗号分隔（如 40100,40200）")
    parser.add_argument("--days", type=int, default=None, help="最近 N 天")
    parser.add_argument("--max", type=int, default=5, help="最多获取多少条")
    parser.add_argument("--download-pdf", action="store_true", help="下载 PDF")
    parser.add_argument("--full", action="store_true", help="完整刷新（忽略缓存）")
    args = parser.parse_args()

    if args.stocks:
        os.environ["HKEX_STOCKS"] = args.stocks
    if args.keywords:
        os.environ["HKEX_KEYWORDS"] = args.keywords
    if args.t1_codes:
        os.environ["HKEX_T1_CODES"] = args.t1_codes
    if args.t2_codes:
        os.environ["HKEX_T2_CODES"] = args.t2_codes
    if args.days is not None:
        os.environ["HKEX_DAYS"] = str(args.days)
    os.environ["HKEX_MAX_ITEMS"] = str(args.max)
    os.environ["HKEX_DOWNLOAD_PDF"] = "true" if args.download_pdf else "false"

    generator = HkexFinancialReportsGenerator()
    result = generator.run(full_refresh=args.full, max_articles=args.max)
    if result:
        print("\n[OK] 成功生成RSS feed")
    else:
        print("\n[ERROR] 生成失败")


if __name__ == "__main__":
    main()
