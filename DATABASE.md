# 資料庫設計

## 1. 基本概念
本專案使用 SQLAlchemy 管理資料模型，資料庫初期為 SQLite，後續可轉換成 PostgreSQL。

## 2. 主要資料表
### news_articles
- id
- title
- source_name
- source_url
- published_at
- collected_at
- summary
- industry
- accident_type
- incident_date
- location
- death_count
- injury_count
- verification_status
- content_hash
- is_test_data
- last_updated_at

### regulations
- id
- name
- authority
- regulation_type
- announcement_type
- status
- notice_date
- notice_deadline
- published_date
- effective_date
- abolished_date
- official_url
- source_url
- summary
- collected_at
- last_confirmed_at
- manual_review_status
- source_name

### data_sources
- id
- name
- source_type
- website_url
- rss_or_api_url
- is_enabled
- last_success_at
- last_failure_at
- last_error
- notes

### update_logs
- id
- source_name
- source_type
- started_at
- finished_at
- status
- items_found
- new_items
- updated_items
- failed_items
- error_message

## 3. 唯一性與索引
- news_articles: source_url 唯一
- data_sources: name 唯一
- regulations: name + published_date 唯一（同一法規同一公布日不重覆）

## 4. 備份與還原
```powershell
copy site.db site.db.bak
copy site.db.bak site.db
```

## 5. 轉 PostgreSQL
新增 `DATABASE_URL` 環境變數後，改用 SQLAlchemy 的 PostgreSQL 協定即可。
