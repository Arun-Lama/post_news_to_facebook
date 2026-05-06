from __future__ import annotations

from urllib.parse import parse_qs, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def sharesansar_latest_pages(pages: int = 5, start_cursor: str | None = None) -> pd.DataFrame:
    """
    Scrape Sharesansar latest news using the same cursor-based XHR endpoint
    the site uses for pagination.

    - If start_cursor is None, starts from the first page (/category/latest).
    - Otherwise starts from /category/latest?cursor=<start_cursor>
    """
    if pages <= 0:
        return pd.DataFrame(columns=["Published Date", "News", "URL"])

    base_url = "https://www.sharesansar.com/category/latest"
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Referer": "https://www.sharesansar.com/category/latest",
    }

    all_rows: list[dict] = []
    cursor = start_cursor

    for _ in range(pages):
        url = base_url if not cursor else f"{base_url}?cursor={cursor}"
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select("div.featured-news-list.margin-bottom-15"):
            title_a = item.find("a", title=True)
            title_h4 = title_a.find("h4", class_="featured-news-title") if title_a else None
            date_span = item.find("span", class_="text-org")

            title = title_h4.get_text(strip=True) if title_h4 else ""
            link = title_a.get("href", "").strip() if title_a else ""
            published = date_span.get_text(strip=True) if date_span else ""

            if title or link or published:
                all_rows.append(
                    {
                        "Published Date": published,
                        "News": title,
                        "URL": link,
                    }
                )

        next_a = soup.select_one('ul.pagination a.page-link[rel="next"]')
        if not next_a or not next_a.get("href"):
            break

        next_url = urljoin(base_url, next_a["href"])
        next_qs = parse_qs(urlparse(next_url).query)
        next_cursor_vals = next_qs.get("cursor")
        cursor = next_cursor_vals[0] if next_cursor_vals else None

        if not cursor:
            break

    return pd.DataFrame(all_rows, columns=["Published Date", "News", "URL"])


def sharesansar_announcement_pages(pages: int = 5, start_cursor: str | None = None) -> pd.DataFrame:
    """
    Scrape Sharesansar announcements using the cursor-based XHR endpoint.

    - If start_cursor is None, starts from the first page (/announcement).
    - Otherwise starts from /announcement?cursor=<start_cursor>
    """
    if pages <= 0:
        return pd.DataFrame(columns=["Published Date", "Announcement", "URL"])

    base_url = "https://www.sharesansar.com/announcement"
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "*/*",
        "Referer": "https://www.sharesansar.com/announcement",
    }

    all_rows: list[dict] = []
    cursor = start_cursor

    for _ in range(pages):
        url = base_url if not cursor else f"{base_url}?cursor={cursor}"
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select("div.featured-news-list.margin-bottom-15"):
            title_a = item.find("a", title=True)
            title_h4 = title_a.find("h4", class_="featured-announcement-title") if title_a else None
            date_span = item.find("span", class_="text-org")

            title = title_h4.get_text(strip=True) if title_h4 else ""
            link = title_a.get("href", "").strip() if title_a else ""
            published = date_span.get_text(strip=True) if date_span else ""

            if title or link or published:
                all_rows.append(
                    {
                        "Published Date": published,
                        "Announcement": title,
                        "URL": link,
                    }
                )

        next_a = soup.select_one('ul.pagination a.page-link[rel="next"]')
        if not next_a or not next_a.get("href"):
            break

        next_url = urljoin(base_url, next_a["href"])
        next_qs = parse_qs(urlparse(next_url).query)
        next_cursor_vals = next_qs.get("cursor")
        cursor = next_cursor_vals[0] if next_cursor_vals else None

        if not cursor:
            break

    return pd.DataFrame(all_rows, columns=["Published Date", "Announcement", "URL"])


def _existing_issues_dataframe(issue_type: int, start: int = 0, length: int = 20) -> pd.DataFrame:
    """``issue_type`` 1 = IPO, 3 = right share (DataTables ``/existing-issues``)."""
    url = "https://www.sharesansar.com/existing-issues"
    params = {
        "draw": 1,
        "start": start,
        "length": length,
        "type": issue_type,
        "search[value]": "",
        "search[regex]": "false",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.sharesansar.com/existing-issues",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    rows = (resp.json().get("data") or [])

    cleaned: list[dict] = []
    for r in rows:
        company = r.get("company") or {}
        cleaned.append(
            {
                "Symbol": _strip_html(company.get("symbol", "")),
                "Company": _strip_html(company.get("companyname", "")),
                "Share Type": r.get("displayable_share_type", ""),
                "Ratio": r.get("ratio_value", ""),
                "Total Units": r.get("total_units", ""),
                "Issue Price": r.get("issue_price", ""),
                "Price Range": r.get("price_range", ""),
                "Cutoff Price": r.get("cutoff_price", ""),
                "Opening Date": r.get("opening_date", ""),
                "Closing Date": r.get("closing_date", ""),
                "Final Date": r.get("final_date", ""),
                "Listing Date": r.get("listing_date", ""),
                "Issue Manager": r.get("issue_manager", ""),
                "Status": r.get("status", ""),
                "Right Eligibility Link": r.get("right_eligibility_link", ""),
                "Announcement Link": r.get("announcement_link", ""),
            }
        )

    return pd.DataFrame(cleaned)


def sharesansar_existing_issues_many_pages(
    issue_type: int, max_pages: int = 40, page_size: int = 20
) -> pd.DataFrame:
    """Concatenate DataTables pages for IPO (``1``) or right share (``3``)."""
    parts: list[pd.DataFrame] = []
    for i in range(max_pages):
        df = _existing_issues_dataframe(issue_type, start=i * page_size, length=page_size)
        if df.empty:
            break
        parts.append(df)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def sharesansar_auction_many_pages(
    auction_type: int, max_pages: int = 40, page_size: int = 20
) -> pd.DataFrame:
    """Concatenate auction DataTables pages (``0`` ordinary, ``1`` promoter)."""
    parts: list[pd.DataFrame] = []
    for i in range(max_pages):
        df = sharesansar_auction_page(auction_type, start=i * page_size, length=page_size)
        if df.empty:
            break
        parts.append(df)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def sharesansar_auction_page(auction_type: int, start: int = 0, length: int = 20) -> pd.DataFrame:
    """
    Fetch one DataTables page from Sharesansar auction JSON.

    ``auction_type`` matches the site tabs:
    - ``0`` — ordinary share auction
    - ``1`` — promoter share auction
    """
    url = "https://www.sharesansar.com/auction"
    params = {
        "draw": 1,
        "start": start,
        "length": length,
        "type": auction_type,
        "search[value]": "",
        "search[regex]": "false",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/147.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.sharesansar.com/auction",
    }

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    rows = (resp.json().get("data") or [])

    cleaned: list[dict] = []
    for r in rows:
        company = r.get("company") or {}
        cleaned.append(
            {
                "Symbol": _strip_html(company.get("symbol", "")),
                "Company": _strip_html(company.get("companyname", "")),
                "Share Type": r.get("displayable_share_type", ""),
                "Total Auction": r.get("total_auction", ""),
                "Total Allotted": r.get("total_alloted", ""),
                "Opening Date": r.get("opening_date", ""),
                "Closing Date": r.get("closing_date", ""),
                "Bid Opening Date": r.get("bid_opening_date", ""),
                "Last Day Auction Price": r.get("last_day_auction_price", ""),
                "Issue Manager": r.get("issue_manager", ""),
                "Cut Off Price": r.get("cut_off_price", ""),
                "LTP": r.get("ltp", ""),
                "Status": r.get("status", ""),
                "Announcement Date": r.get("announcement_date", ""),
                "Announcement Link": r.get("announcement_link", ""),
            }
        )

    return pd.DataFrame(cleaned)
