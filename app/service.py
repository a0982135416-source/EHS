from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from app.models import (
    CLASSIFICATION_PENDING,
    REVIEW_STATUS_PENDING,
    DataSource,
    NewsArticle,
    Regulation,
    UpdateLog,
    db,
)
from app.news_sources import fetch_mol_news, fetch_osha_news
from app.regulation_sources import fetch_mol_law_news, fetch_moj_news
from app.utils import log_source_failure, log_update, sanitize_text


def normalize_news_record(item: dict[str, Any]) -> dict[str, Any]:
    title = sanitize_text(item.get("title") or "")
    source_url = sanitize_text(item.get("source_url") or "")
    if not title or not source_url:
        raise ValueError("新聞項目缺少標題或來源網址")
    source_name = sanitize_text(item.get("source_name") or "未知來源")
    summary = sanitize_text(item.get("summary") or "")
    published = item.get("published_at")
    if published is None:
        published = datetime.utcnow()
    return {
        "title": title,
        "source_name": source_name,
        "source_url": source_url,
        "published_at": published,
        "summary": summary,
        "content_hash": item.get("content_hash") or hashlib.sha256(f"{title}|{source_url}".encode("utf-8")).hexdigest(),
        "industry": CLASSIFICATION_PENDING,
        "accident_type": CLASSIFICATION_PENDING,
        "verification_status": REVIEW_STATUS_PENDING,
    }


def normalize_regulation_record(item: dict[str, Any]) -> dict[str, Any]:
    name = sanitize_text(item.get("name") or "")
    if not name:
        raise ValueError("法規項目缺少名稱")
    return {
        "name": name,
        "authority": sanitize_text(item.get("authority") or REVIEW_STATUS_PENDING),
        "regulation_type": sanitize_text(item.get("regulation_type") or REVIEW_STATUS_PENDING),
        "announcement_type": sanitize_text(item.get("announcement_type") or REVIEW_STATUS_PENDING),
        "status": sanitize_text(item.get("status") or REVIEW_STATUS_PENDING),
        "notice_date": item.get("notice_date"),
        "notice_deadline": item.get("notice_deadline"),
        "published_date": item.get("published_date"),
        "effective_date": item.get("effective_date"),
        "abolished_date": item.get("abolished_date"),
        "official_url": item.get("official_url") or item.get("source_url"),
        "source_url": item.get("source_url") or item.get("official_url"),
        "summary": sanitize_text(item.get("summary") or ""),
        "source_name": sanitize_text(item.get("source_name") or "未知來源"),
        "manual_review_status": REVIEW_STATUS_PENDING,
    }


def store_news_items(items: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = 0
    for item in items:
        record = normalize_news_record(item)
        if NewsArticle.query.filter_by(content_hash=record["content_hash"]).first():
            continue
        article = NewsArticle(**record)
        db.session.add(article)
        inserted += 1
    db.session.commit()
    return len(items), inserted


def store_regulation_items(items: list[dict[str, Any]]) -> tuple[int, int]:
    inserted = 0
    for item in items:
        record = normalize_regulation_record(item)
        existing = Regulation.query.filter_by(name=record["name"]).first()
        if existing is not None:
            continue
        regulation = Regulation(**record)
        db.session.add(regulation)
        inserted += 1
    db.session.commit()
    return len(items), inserted


def upsert_source_status(source_name: str, source_type: str, *, ok: bool, error_message: str | None = None) -> None:
    source = DataSource.query.filter_by(name=source_name).first()
    if source is None:
        source = DataSource(name=source_name, source_type=source_type, is_enabled=True)
        db.session.add(source)
    source.is_enabled = True
    source.last_error = error_message
    if ok:
        source.last_success_at = datetime.utcnow()
    else:
        source.last_failure_at = datetime.utcnow()
    db.session.commit()


def record_update_result(source_name: str, source_type: str, *, status: str, items_found: int, new_items: int, error_message: str | None = None) -> None:
    log = UpdateLog(
        source_name=source_name,
        source_type=source_type,
        status=status,
        items_found=items_found,
        new_items=new_items,
        updated_items=0,
        failed_items=max(0, items_found - new_items),
        error_message=error_message,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.session.add(log)
    db.session.commit()


def _source_name_for_fetcher(fetcher_name: str, kind: str) -> str:
    mapping = {
        "news": {
            "fetch_mol_news": "勞動部全球資訊網",
            "fetch_osha_news": "勞動部職業安全衛生署",
        },
        "regulation": {
            "fetch_mol_law_news": "勞動部勞動法令查詢系統",
            "fetch_moj_news": "全國法規資料庫",
        },
    }
    return mapping.get(kind, {}).get(fetcher_name, fetcher_name)


def run_news_ingest() -> dict[str, Any]:
    results = {"items_found": 0, "new_items": 0, "errors": []}
    for fetcher in (fetch_mol_news, fetch_osha_news):
        source_name = _source_name_for_fetcher(fetcher.__name__, "news")
        try:
            fetched = fetcher()
            if not fetched:
                raise ValueError("來源未返回可用資料")
            total, inserted = store_news_items(fetched)
            results["items_found"] += total
            results["new_items"] += inserted
            upsert_source_status(source_name, "news", ok=True)
            record_update_result(source_name, "news", status="success", items_found=total, new_items=inserted)
            log_source_failure(source_name, "") if False else None
        except Exception as exc:
            results["errors"].append({"source": source_name, "error": str(exc)})
            upsert_source_status(source_name, "news", ok=False, error_message=str(exc))
            record_update_result(source_name, "news", status="failed", items_found=0, new_items=0, error_message=str(exc))
            log_source_failure(source_name, str(exc), source_type="news")
            log_update(source_name, source_type="news", status="failed", items_found=0, new_items=0, error_message=str(exc))
    return results


def run_regulation_ingest() -> dict[str, Any]:
    results = {"items_found": 0, "new_items": 0, "errors": []}
    for fetcher in (fetch_mol_law_news, fetch_moj_news):
        source_name = _source_name_for_fetcher(fetcher.__name__, "regulation")
        try:
            fetched = fetcher()
            if not fetched:
                raise ValueError("來源未返回可用資料")
            total, inserted = store_regulation_items(fetched)
            results["items_found"] += total
            results["new_items"] += inserted
            upsert_source_status(source_name, "regulation", ok=True)
            record_update_result(source_name, "regulation", status="success", items_found=total, new_items=inserted)
        except Exception as exc:
            results["errors"].append({"source": source_name, "error": str(exc)})
            upsert_source_status(source_name, "regulation", ok=False, error_message=str(exc))
            record_update_result(source_name, "regulation", status="failed", items_found=0, new_items=0, error_message=str(exc))
            log_source_failure(source_name, str(exc), source_type="regulation")
            log_update(source_name, source_type="regulation", status="failed", items_found=0, new_items=0, error_message=str(exc))
    return results
