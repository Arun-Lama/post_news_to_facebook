"""
Build a plain-text Facebook post from Sharesansar scrapers and save ``content.txt``.

Run (from this folder): ``python build_facebook_content.py``
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

from sharesansar_news import (
    sharesansar_announcement_pages,
    sharesansar_auction_many_pages,
    sharesansar_existing_issues_many_pages,
    sharesansar_latest_pages,
)

NEWS_LIST_URL = "https://www.sharesansar.com/category/latest"
ANNOUNCEMENTS_LIST_URL = "https://www.sharesansar.com/announcement"
EXISTING_ISSUES_URL = "https://www.sharesansar.com/existing-issues"
AUCTION_URL = "https://www.sharesansar.com/auction"

_SHORT_CACHE: dict[str, str] = {}


def shorten_url(url: str) -> str:
    """Shorten via is.gd; on failure return the original URL. Deduplicates within the run."""
    url = (url or "").strip()
    if not url.startswith("http"):
        return url
    if url in _SHORT_CACHE:
        return _SHORT_CACHE[url]
    api = "https://is.gd/create.php?format=simple&url=" + urllib.parse.quote(url, safe="")
    try:
        r = requests.get(api, timeout=15)
        text = (r.text or "").strip()
        if r.ok and text.startswith("http") and not text.lower().startswith("error"):
            _SHORT_CACHE[url] = text
            time.sleep(0.25)
            return text
    except OSError:
        pass
    _SHORT_CACHE[url] = url
    return url


def _parse_published_date(value: object) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%A, %B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def filter_last_n_calendar_dates(df: pd.DataFrame, date_col: str, n: int = 2) -> pd.DataFrame:
    """Keep rows whose ``date_col`` falls on the ``n`` most recent calendar dates present, newest first."""
    if df.empty or date_col not in df.columns:
        return df.head(0)
    work = df.copy()
    work["_dt"] = work[date_col].map(_parse_published_date)
    parsed = work.dropna(subset=["_dt"])
    if parsed.empty:
        return df.head(0)
    unique_dates = sorted(parsed["_dt"].unique(), reverse=True)
    keep = set(unique_dates[:n])
    out = parsed[parsed["_dt"].isin(keep)].sort_values(by="_dt", ascending=False, kind="mergesort")
    return out.drop(columns=["_dt"], errors="ignore")


def _status_to_int(value: object) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _ipo_style_label(code: int | None) -> str:
    if code is None:
        return ""
    return {0: "Open", -1: "Coming Soon", 1: "Closed", -2: ""}.get(code, str(code))


def _format_news(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    lines = [
        "📰 Latest market news",
        f"🔗 Open news: {shorten_url(NEWS_LIST_URL)}",
        "",
    ]
    last_date_label: str | None = None
    for _, row in df.iterrows():
        date_label = str(row.get("Published Date", "") or "").strip()
        title = str(row.get("News", "") or "").strip()
        url = str(row.get("URL", "") or "").strip()
        if not title:
            continue
        if date_label and date_label != last_date_label:
            if last_date_label is not None:
                lines.append("")
            lines.append(f"📅 {date_label}")
            last_date_label = date_label
        lines.append(f"  📌 {title}")
        if url:
            lines.append(f"     🔗 {shorten_url(url)}")
    return "\n".join(lines)


def _format_announcements(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    lines = ["Announcements:", f"Open news: {shorten_url(ANNOUNCEMENTS_LIST_URL)}"]
    for _, row in df.iterrows():
        text = str(row.get("Announcement", "") or "").strip()
        if not text:
            continue
        lines.append(f"- {text}")
        url = str(row.get("URL", "") or "").strip()
        if url:
            lines.append(f"  {shorten_url(url)}")
    return "\n".join(lines)


def _format_right_share(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    df = df.copy()
    df["_st"] = df["Status"].map(_status_to_int)
    sub = df[df["_st"].isin((0, -1))]
    if sub.empty:
        return None
    lines = [
        "Right share (Open / Coming Soon):",
        f"Open table: {shorten_url(EXISTING_ISSUES_URL)}",
    ]
    for _, row in sub.iterrows():
        label = _ipo_style_label(_status_to_int(row["Status"]))
        lines.append(
            f"- [{label}] Symbol: {row.get('Symbol', '')} | Opening Date: {row.get('Opening Date', '')} | "
            f"Closing Date: {row.get('Closing Date', '')} | Book Closure Date: {row.get('Final Date', '')}"
        )
    return "\n".join(lines)


def _format_ipo(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    df = df.copy()
    df["_st"] = df["Status"].map(_status_to_int)
    sub = df[df["_st"].isin((0, -1))]
    if sub.empty:
        return None
    lines = [
        "IPO (Open / Coming Soon):",
        f"Open table: {shorten_url(EXISTING_ISSUES_URL)}",
    ]
    for _, row in sub.iterrows():
        label = _ipo_style_label(_status_to_int(row["Status"]))
        lines.append(
            f"- [{label}] Symbol: {row.get('Symbol', '')} | Opening Date: {row.get('Opening Date', '')} | "
            f"Closing Date: {row.get('Closing Date', '')} | Last Closing Date: {row.get('Final Date', '')}"
        )
    return "\n".join(lines)


def _format_auction(df: pd.DataFrame, heading: str) -> str | None:
    if df.empty:
        return None
    df = df.copy()
    df["_st"] = df["Status"].map(_status_to_int)
    sub = df[df["_st"] == 0]
    if sub.empty:
        return None
    lines = [heading, f"Open table: {shorten_url(AUCTION_URL)}"]
    for _, row in sub.iterrows():
        lines.append(
            f"- Symbol: {row.get('Symbol', '')} | Opening Date: {row.get('Opening Date', '')} | "
            f"Closing Date: {row.get('Closing Date', '')}"
        )
    return "\n".join(lines)


def build_facebook_post_text() -> str:
    _SHORT_CACHE.clear()

    news_df = sharesansar_latest_pages(pages=5)
    news_df = filter_last_n_calendar_dates(news_df, "Published Date", 2)

    ann_df = sharesansar_announcement_pages(pages=5)
    ann_df = filter_last_n_calendar_dates(ann_df, "Published Date", 2)

    right_df = sharesansar_existing_issues_many_pages(3, max_pages=10)
    ipo_df = sharesansar_existing_issues_many_pages(1, max_pages=10)
    auction_ord_df = sharesansar_auction_many_pages(0, max_pages=10)
    auction_pro_df = sharesansar_auction_many_pages(1, max_pages=10)

    parts: list[str] = []
    for block in (
        _format_news(news_df),
        _format_announcements(ann_df),
        _format_right_share(right_df),
        _format_ipo(ipo_df),
        _format_auction(auction_ord_df, "Auction - ordinary share (Open):"),
        _format_auction(auction_pro_df, "Auction - promoter share (Open):"),
    ):
        if block:
            parts.append(block)

    return "\n\n".join(parts).strip() + "\n"


def write_content_txt(out_path: Path | None = None) -> Path:
    if out_path is None:
        out_path = Path(__file__).resolve().parent / "content.txt"
    text = build_facebook_post_text()
    out_path.write_text(text, encoding="utf-8")
    return out_path


def main() -> None:
    path = write_content_txt()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
