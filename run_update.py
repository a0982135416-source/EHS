from __future__ import annotations

from datetime import datetime

from app import create_app
from app.collectors import fetch_feed_entries, mark_source_failure, mark_source_success, register_source_if_missing
from app.service import run_news_ingest, run_regulation_ingest
from app.sources import OFFICIAL_NEWS_SOURCES, OFFICIAL_REGULATION_SOURCES


def run_update():
    app = create_app()
    with app.app_context():
        for source in OFFICIAL_NEWS_SOURCES + OFFICIAL_REGULATION_SOURCES:
            register_source_if_missing(
                name=source["name"],
                source_type=source["source_type"],
                website_url=source.get("website_url"),
                rss_or_api_url=source.get("rss_or_api_url"),
                notes=source.get("notes"),
            )
        try:
            news_result = run_news_ingest()
            regulation_result = run_regulation_ingest()
            if news_result["errors"] or regulation_result["errors"]:
                print("[WARN] 部分來源更新失敗，請檢查 update_logs 與 DataSource 記錄。")
            for entry in news_result["errors"] + regulation_result["errors"]:
                print(f"[ERROR] {entry['source']}: {entry['error']}")
        except Exception as exc:
            print(f"[ERROR] update process failed: {exc}")
            for source in OFFICIAL_NEWS_SOURCES + OFFICIAL_REGULATION_SOURCES:
                mark_source_failure(source["name"], str(exc))


if __name__ == "__main__":
    run_update()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] update run completed.")
