from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

from .models import DataSource, UpdateLog, db


def sanitize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_valid_external_url(value: str | None) -> bool:
    if not value:
        return False
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not re.match(r"^https?://", value):
        return False
    if "://" not in value:
        return False
    return bool(re.match(r"^https?://[A-Za-z0-9.-]+(?::\d+)?(?:/.*)?$", value))


def log_source_failure(source_name: str, error_message: str, source_type: str = "news") -> DataSource | None:
    source = DataSource.query.filter_by(name=source_name).first()
    if source is None:
        source = DataSource(name=source_name, source_type=source_type, is_enabled=True)
        db.session.add(source)
    source.last_failure_at = datetime.now(timezone.utc)
    source.last_error = error_message
    source.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return source


def log_update(source_name: str, *, source_type: str, status: str, items_found: int = 0, new_items: int = 0, updated_items: int = 0, failed_items: int = 0, error_message: str | None = None) -> UpdateLog:
    log = UpdateLog(
        source_name=source_name,
        source_type=source_type,
        status=status,
        items_found=items_found,
        new_items=new_items,
        updated_items=updated_items,
        failed_items=failed_items,
        error_message=error_message,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.session.add(log)
    db.session.commit()
    return log


def compare_regulation_texts(old_text: str | None, new_text: str | None) -> dict[str, Any]:
    old_text = old_text or ""
    new_text = new_text or ""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    added = [line for line in new_lines if line not in old_lines]
    removed = [line for line in old_lines if line not in new_lines]
    changed = old_text != new_text
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "old_text": old_text,
        "new_text": new_text,
        "summary": "條文內容已更新，需人工確認。",
        "change_type": "modified" if changed else "unchanged",
    }
