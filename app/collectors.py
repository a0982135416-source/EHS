from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

from .models import DataSource, db

REQUEST_TIMEOUT = 15


def fetch_feed_entries(feed_url: str) -> list[dict[str, Any]]:
    if not feed_url:
        return []
    try:
        response = requests.get(feed_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        parsed = feedparser.parse(response.text)
        entries = []
        for item in parsed.entries:
            entries.append(
                {
                    "title": getattr(item, "title", "") or "",
                    "link": getattr(item, "link", "") or "",
                    "summary": getattr(item, "summary", "") or "",
                    "published": getattr(item, "published_parsed", None),
                }
            )
        return entries
    except Exception:
        return []


def register_source_if_missing(name: str, source_type: str, website_url: str | None = None, rss_or_api_url: str | None = None, notes: str | None = None) -> DataSource:
    source = DataSource.query.filter_by(name=name).first()
    if source is None:
        source = DataSource(
            name=name,
            source_type=source_type,
            website_url=website_url,
            rss_or_api_url=rss_or_api_url,
            is_enabled=False,
            notes=notes,
        )
        db.session.add(source)
        db.session.commit()
    return source


def mark_source_success(source_name: str) -> None:
    source = DataSource.query.filter_by(name=source_name).first()
    if source is not None:
        source.last_success_at = datetime.now(timezone.utc)
        source.last_error = None
        source.updated_at = datetime.now(timezone.utc)
        db.session.commit()


def mark_source_failure(source_name: str, error_message: str) -> None:
    source = DataSource.query.filter_by(name=source_name).first()
    if source is None:
        return
    source.last_failure_at = datetime.now(timezone.utc)
    source.last_error = error_message
    source.updated_at = datetime.now(timezone.utc)
    db.session.commit()
