from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any

import feedparser
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REQUEST_TIMEOUT = 20
REQUESTS_VERIFY_SSL = os.getenv("REQUESTS_VERIFY_SSL", "false").strip().lower() not in {"0", "false", "no"}

MOL_RSS_URL = "https://www.mol.gov.tw/1607/1632/1633/RssList"
OSHA_RSS_URL = "https://www.osha.gov.tw/48110/48417/48419/RssList"


def _safe_get(url: str) -> requests.Response:
    return requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0"},
        verify=REQUESTS_VERIFY_SSL,
    )


def _parse_published(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            parsed = feedparser._parse_date(value)
            if parsed:
                return parsed
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def fetch_mol_news() -> list[dict[str, Any]]:
    response = _safe_get(MOL_RSS_URL)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        title = (getattr(entry, "title", "") or "").strip()
        link = (getattr(entry, "link", "") or "").strip()
        if not title or not link:
            continue
        summary = (getattr(entry, "summary", "") or getattr(entry, "description", "") or "").strip()
        published = _parse_published(getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None) or getattr(entry, "published", None))
        items.append(
            {
                "source_name": "勞動部全球資訊網",
                "source_url": link,
                "title": title,
                "summary": summary,
                "published_at": published,
                "content_hash": hashlib.sha256(f"{title}|{link}".encode("utf-8")).hexdigest(),
            }
        )
    return items


def fetch_osha_news() -> list[dict[str, Any]]:
    response = _safe_get(OSHA_RSS_URL)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        title = (getattr(entry, "title", "") or "").strip()
        link = (getattr(entry, "link", "") or "").strip()
        if not title or not link:
            continue
        summary = (getattr(entry, "summary", "") or getattr(entry, "description", "") or "").strip()
        published = _parse_published(getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None) or getattr(entry, "published", None))
        items.append(
            {
                "source_name": "勞動部職業安全衛生署",
                "source_url": link,
                "title": title,
                "summary": summary,
                "published_at": published,
                "content_hash": hashlib.sha256(f"{title}|{link}".encode("utf-8")).hexdigest(),
            }
        )
    return items
