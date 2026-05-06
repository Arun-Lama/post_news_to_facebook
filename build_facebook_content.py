"""
Build a Sharesansar digest for Facebook, save ``content.html`` (UTF-8 preview with emojis),
and expose the same body as plain text for the Graph API ``message`` field.

Run (from this folder): ``python build_facebook_content.py``
"""

from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path

import pandas as pd

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


def _cell(row: object, key: str) -> str:
    """Single table cell as plain text; empty if missing or NaN."""
    if not hasattr(row, "get"):
        return ""
    v = row.get(key, "")
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return ""
    return s


def _format_news(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    lines = [
        "🧠 Market Pulse Nepal: What Investors Need to Know Today",
        f"({datetime.now().strftime('%A, %B %d, %Y')})",
        "",
    ]
    last_date_label: str | None = None
    had_story_under_date = False
    for _, row in df.iterrows():
        date_label = str(row.get("Published Date", "") or "").strip()
        title = str(row.get("News", "") or "").strip()
        if not title:
            continue
        if date_label and date_label != last_date_label:
            if last_date_label is not None:
                lines.append("")
            lines.append(f"📅 {date_label}")
            last_date_label = date_label
            had_story_under_date = False
        if had_story_under_date:
            lines.append("")
        lines.append(f"  📌 {title}")
        had_story_under_date = True
    return "\n".join(lines)


def _format_announcements(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    lines = [
        "Announcements",
        "",
    ]
    first = True
    for _, row in df.iterrows():
        text = str(row.get("Announcement", "") or "").strip()
        if not text:
            continue
        if not first:
            lines.append("")
        first = False
        lines.append(f"• {text}")
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
        "Right share (open or coming soon)",
        "",
    ]
    first = True
    for _, row in sub.iterrows():
        label = _ipo_style_label(_status_to_int(row["Status"]))
        sym = _cell(row, "Symbol")
        if not sym:
            continue
        if not first:
            lines.append("")
        first = False
        lines.append(f"• {sym} — {label}")
        od, cd, bc = _cell(row, "Opening Date"), _cell(row, "Closing Date"), _cell(row, "Final Date")
        if od:
            lines.append(f"  Opens: {od}")
        if cd:
            lines.append(f"  Closes: {cd}")
        if bc:
            lines.append(f"  Book closure: {bc}")
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
        "IPO (open or coming soon)",
        "",
    ]
    first = True
    for _, row in sub.iterrows():
        label = _ipo_style_label(_status_to_int(row["Status"]))
        sym = _cell(row, "Symbol")
        if not sym:
            continue
        if not first:
            lines.append("")
        first = False
        lines.append(f"• {sym} — {label}")
        od, cd, lcd = _cell(row, "Opening Date"), _cell(row, "Closing Date"), _cell(row, "Final Date")
        if od:
            lines.append(f"  Opens: {od}")
        if cd:
            lines.append(f"  Closes: {cd}")
        if lcd:
            lines.append(f"  Last close: {lcd}")
    return "\n".join(lines)


def _format_auction(df: pd.DataFrame, heading: str) -> str | None:
    if df.empty:
        return None
    df = df.copy()
    df["_st"] = df["Status"].map(_status_to_int)
    sub = df[df["_st"] == 0]
    if sub.empty:
        return None
    lines = [heading, ""]
    first = True
    for _, row in sub.iterrows():
        sym = _cell(row, "Symbol")
        if not sym:
            continue
        if not first:
            lines.append("")
        first = False
        lines.append(f"• {sym}")
        od, cd = _cell(row, "Opening Date"), _cell(row, "Closing Date")
        if od:
            lines.append(f"  Opens: {od}")
        if cd:
            lines.append(f"  Closes: {cd}")
    return "\n".join(lines)


def _format_source_links(
    *,
    has_news: bool,
    has_announcements: bool,
    has_existing_issues: bool,
    has_auction: bool,
) -> str | None:
    """One full URL per source page, listed once at the end."""
    rows: list[tuple[str, str]] = []
    if has_news:
        rows.append(("Latest news (Sharesansar)", NEWS_LIST_URL))
    if has_announcements:
        rows.append(("Announcements", ANNOUNCEMENTS_LIST_URL))
    if has_existing_issues:
        rows.append(("Right shares & IPOs — existing issues", EXISTING_ISSUES_URL))
    if has_auction:
        rows.append(("Auctions", AUCTION_URL))
    if not rows:
        return None
    lines = ["────────", "Source pages", ""]
    for label, url in rows:
        lines.append(f"{label}: {url}")
    return "\n".join(lines)


def build_facebook_post_text() -> str:
    news_df = sharesansar_latest_pages(pages=5)
    news_df = filter_last_n_calendar_dates(news_df, "Published Date", 2)

    ann_df = sharesansar_announcement_pages(pages=5)
    ann_df = filter_last_n_calendar_dates(ann_df, "Published Date", 2)

    right_df = sharesansar_existing_issues_many_pages(3, max_pages=10)
    ipo_df = sharesansar_existing_issues_many_pages(1, max_pages=10)
    auction_ord_df = sharesansar_auction_many_pages(0, max_pages=10)
    auction_pro_df = sharesansar_auction_many_pages(1, max_pages=10)

    block_news = _format_news(news_df)
    block_ann = _format_announcements(ann_df)
    block_right = _format_right_share(right_df)
    block_ipo = _format_ipo(ipo_df)
    block_auc_ord = _format_auction(auction_ord_df, "Auction — ordinary share (open)")
    block_auc_pro = _format_auction(auction_pro_df, "Auction — promoter share (open)")

    parts: list[str] = []
    for block in (
        block_news,
        block_ann,
        block_right,
        block_ipo,
        block_auc_ord,
        block_auc_pro,
    ):
        if block:
            parts.append(block)

    links = _format_source_links(
        has_news=block_news is not None,
        has_announcements=block_ann is not None,
        has_existing_issues=block_right is not None or block_ipo is not None,
        has_auction=block_auc_ord is not None or block_auc_pro is not None,
    )
    if links:
        parts.append(links)

    return "\n\n".join(parts).strip() + "\n"


def _plain_to_html_document(plain: str) -> str:
    """Minimal HTML5 wrapper so browsers show emojis and line breaks correctly."""
    body = html.escape(plain, quote=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Facebook digest preview</title>
  <style>
    body {{ font-family: system-ui, "Segoe UI", Roboto, sans-serif; margin: 1rem; background: #f6f6f6; color: #111; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.95rem; line-height: 1.5;
           background: #fff; padding: 1rem 1.1rem; border-radius: 10px; border: 1px solid #e4e4e4; }}
  </style>
</head>
<body>
<pre>{body}</pre>
</body>
</html>
"""


def write_content_html(out_path: Path | None = None) -> tuple[str, Path]:
    """Write ``content.html`` and return ``(plain_text, path)`` for the same digest."""
    if out_path is None:
        out_path = Path(__file__).resolve().parent / "content.html"
    plain = build_facebook_post_text()
    out_path.write_text(_plain_to_html_document(plain), encoding="utf-8")
    return plain, out_path


def main() -> None:
    _, path = write_content_html()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
