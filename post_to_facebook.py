"""
Build the Sharesansar digest (``content.html``) and optionally post plain text to the Page.

Posting is controlled by:

- ``FACEBOOK_POST`` env: ``1`` / ``true`` / ``yes`` / ``on`` = post (default if unset).
  ``0`` / ``false`` / ``no`` / ``off`` = build only (no Graph API call).
- ``python post_to_facebook.py --no-post`` — always skips posting (handy for local tests).

Uses ``FB_PAGE_ID`` and ``FB_PAGE_ACCESS_TOKEN`` from the environment.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE = Path(__file__).resolve().parent
_CONTENT_HTML = _BASE / "content.html"

# Facebook feed message max length (leave headroom)
_MAX_MESSAGE_CHARS = 62_000


def get_facebook_credentials() -> tuple[str, str]:
    page_id = os.getenv("FB_PAGE_ID")
    access_token = os.getenv("FB_PAGE_ACCESS_TOKEN")

    if not page_id:
        raise RuntimeError(
            "Missing environment variable 'FB_PAGE_ID'. Set it in .env or CI secrets."
        )
    if not access_token:
        raise RuntimeError(
            "Missing environment variable 'FB_PAGE_ACCESS_TOKEN'. "
            "Set it in .env or CI secrets."
        )

    return page_id.strip(), access_token.strip()


def post_text_to_page(message: str, *, api_version: str = "v19.0") -> dict:
    """Publish a plain-text post to the Page feed."""
    page_id, access_token = get_facebook_credentials()

    body = (message or "").strip()
    if not body:
        raise RuntimeError("Cannot post an empty message.")

    if len(body) > _MAX_MESSAGE_CHARS:
        body = body[: _MAX_MESSAGE_CHARS - 80].rstrip() + "\n\n… (truncated for Facebook length limit)"

    url = f"https://graph.facebook.com/{api_version}/{page_id}/feed"
    data = {
        "message": body,
        "access_token": access_token,
    }
    response = requests.post(url, data=data, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"Post failed ({response.status_code}): {response.text}")

    return response.json()


def upload_image_unpublished(image_path: str | Path, page_id: str, access_token: str) -> str:
    """Upload image without publishing; returns media_fbid."""
    url = f"https://graph.facebook.com/v19.0/{page_id}/photos"
    image_path = Path(image_path)

    with open(image_path, "rb") as image_file:
        files = {"source": image_file}
        data = {
            "published": "false",
            "access_token": access_token,
        }
        response = requests.post(url, files=files, data=data, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(
            f"Image upload failed ({response.status_code}): {response.text}"
        )

    return response.json()["id"]


def format_analysis_caption(
    analysis_text: str,
    *,
    headline: str = "📊 सेक्टर मोमेन्टम · Nepse Indices",
    as_of: str | None = None,
    max_length: int = 9000,
) -> str:
    """Format long analysis text for Facebook (charts / Gemini flows)."""
    body = (analysis_text or "").strip()
    body = re.sub(r"\n{3,}", "\n\n", body)

    lines = [headline.strip()]
    if as_of:
        lines.append(f"📅 {as_of}")
    lines.append("")
    lines.append(body)
    lines.append("")
    lines.append(
        "—\n"
        "तकनीकी टिप्पणी मात्र; लगानी सल्लाह होइन।\n"
        "#NEPSE #NepalStockMarket #SectorMomentum #QuantitativeNepse"
    )

    out = "\n".join(lines)
    if len(out) > max_length:
        out = out[: max_length - 20].rstrip() + "\n… (truncated)"
    return out


def post_multiple_images_single_post(
    charts_dir: str | Path,
    caption: str = "📊 Market Charts Summary",
) -> dict | None:
    """Multi-image post (requires ``chart_order`` module and chart files)."""
    try:
        from chart_order import ordered_chart_paths
    except ImportError as exc:
        raise RuntimeError(
            "chart_order is not available. Install or add chart_order.py for chart posts."
        ) from exc

    page_id, access_token = get_facebook_credentials()
    charts_dir = Path(charts_dir)
    image_paths = ordered_chart_paths(charts_dir)

    if not image_paths:
        print("No images found to post.")
        return None

    print(f"Uploading {len(image_paths)} images...")
    media_fbids = []
    for image_path in image_paths:
        print(f"Uploading {image_path.name}")
        media_id = upload_image_unpublished(
            image_path=image_path,
            page_id=page_id,
            access_token=access_token,
        )
        media_fbids.append({"media_fbid": media_id})

    post_url = f"https://graph.facebook.com/v19.0/{page_id}/feed"
    data = {
        "message": caption,
        "attached_media": media_fbids,
        "access_token": access_token,
    }
    response = requests.post(post_url, json=data, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(
            f"Post creation failed ({response.status_code}): {response.text}"
        )
    print("Single multi-image post created successfully.")
    return response.json()


def _facebook_post_enabled() -> bool:
    flag = (os.getenv("FACEBOOK_POST") or "1").strip().lower()
    return flag in ("1", "true", "yes", "on")


def build_and_post_digest(*, no_post: bool = False) -> None:
    """Regenerate ``content.html`` and publish plain text to the Page when enabled."""
    import build_facebook_content as bfc

    plain, out_path = bfc.write_content_html(_CONTENT_HTML)
    print(f"Wrote digest: {out_path}")

    if no_post:
        print("--no-post: skipping Graph API.")
        return

    if not _facebook_post_enabled():
        print("FACEBOOK_POST is off (0/false/no/off); skipping Graph API post.")
        return

    if not plain.strip():
        print("Digest is empty; nothing to post.")
        return

    result = post_text_to_page(plain)
    print("Posted to Facebook:", result.get("id", result))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build digest HTML and optionally post to Facebook.")
    parser.add_argument(
        "--no-post",
        action="store_true",
        help="Build content.html only; never call the Facebook API.",
    )
    args = parser.parse_args()
    build_and_post_digest(no_post=args.no_post)


if __name__ == "__main__":
    main()
