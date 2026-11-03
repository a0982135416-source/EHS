from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

REVIEW_STATUS_PENDING = "待審核"
REVIEW_STATUS_APPROVED = "通過"
REVIEW_STATUS_REVISION_REQUIRED = "待修正"
REVIEW_STATUS_REJECTED = "不通過"
CLASSIFICATION_PENDING = "待分類"


db = SQLAlchemy()


class DataSource(db.Model):
    __tablename__ = "data_sources"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(50), nullable=False, default="news")
    website_url = db.Column(db.String(500), nullable=True)
    rss_or_api_url = db.Column(db.String(500), nullable=True)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    last_success_at = db.Column(db.DateTime, nullable=True)
    last_failure_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("name", name="uq_data_source_name"),)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False, default="審核人員")
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="reviewer")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_login_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class NewsArticle(db.Model):
    __tablename__ = "news_articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    source_name = db.Column(db.String(200), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)
    collected_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    summary = db.Column(db.Text, nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    accident_type = db.Column(db.String(100), nullable=True)
    incident_date = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(200), nullable=True)
    death_count = db.Column(db.Integer, nullable=True)
    injury_count = db.Column(db.Integer, nullable=True)
    verification_status = db.Column(db.String(50), nullable=False, default=REVIEW_STATUS_PENDING, index=True)
    review_status = db.Column(db.String(50), nullable=False, default=REVIEW_STATUS_PENDING, index=True)
    content_hash = db.Column(db.String(128), nullable=False, unique=True)
    is_test_data = db.Column(db.Boolean, nullable=False, default=False)
    last_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("source_url", name="uq_news_source_url"),)


class Regulation(db.Model):
    __tablename__ = "regulations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    authority = db.Column(db.String(200), nullable=True)
    regulation_type = db.Column(db.String(100), nullable=True)
    announcement_type = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(100), nullable=False, default="待確認")
    notice_date = db.Column(db.DateTime, nullable=True)
    notice_deadline = db.Column(db.DateTime, nullable=True)
    published_date = db.Column(db.DateTime, nullable=True)
    effective_date = db.Column(db.DateTime, nullable=True)
    abolished_date = db.Column(db.DateTime, nullable=True)
    official_url = db.Column(db.String(500), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    collected_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_confirmed_at = db.Column(db.DateTime, nullable=True)
    manual_review_status = db.Column(db.String(50), nullable=False, default=REVIEW_STATUS_PENDING)
    review_status = db.Column(db.String(50), nullable=False, default=REVIEW_STATUS_PENDING, index=True)
    source_name = db.Column(db.String(200), nullable=True)

    __table_args__ = (db.UniqueConstraint("name", "published_date", name="uq_regulation_name_published_date"),)


class RegulationVersion(db.Model):
    __tablename__ = "regulation_versions"

    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey("regulations.id"), nullable=False, index=True)
    version_label = db.Column(db.String(100), nullable=False)
    version_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(100), nullable=False, default="待確認")
    body_text = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    official_url = db.Column(db.String(500), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    regulation = db.relationship("Regulation", backref=db.backref("versions", cascade="all, delete-orphan"))

    __table_args__ = (db.UniqueConstraint("regulation_id", "version_label", name="uq_regulation_version_label"),)


class RegulationChange(db.Model):
    __tablename__ = "regulation_changes"

    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey("regulations.id"), nullable=False, index=True)
    from_version_id = db.Column(db.Integer, db.ForeignKey("regulation_versions.id"), nullable=True, index=True)
    to_version_id = db.Column(db.Integer, db.ForeignKey("regulation_versions.id"), nullable=True, index=True)
    article_no = db.Column(db.String(100), nullable=True)
    change_type = db.Column(db.String(80), nullable=False, default="待判定")
    before_text = db.Column(db.Text, nullable=True)
    after_text = db.Column(db.Text, nullable=True)
    difference_marker = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    new_obligations = db.Column(db.Text, nullable=True)
    workflow_impact = db.Column(db.Text, nullable=True)
    review_status = db.Column(db.String(50), nullable=False, default=REVIEW_STATUS_PENDING, index=True)
    official_url = db.Column(db.String(500), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    published_date = db.Column(db.DateTime, nullable=True)
    effective_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    regulation = db.relationship("Regulation", backref=db.backref("changes", cascade="all, delete-orphan"))
    from_version = db.relationship("RegulationVersion", foreign_keys=[from_version_id], backref=db.backref("outgoing_changes", cascade="all, delete-orphan"))
    to_version = db.relationship("RegulationVersion", foreign_keys=[to_version_id], backref=db.backref("incoming_changes", cascade="all, delete-orphan"))


class ReviewRecord(db.Model):
    __tablename__ = "review_records"

    id = db.Column(db.Integer, primary_key=True)
    data_type = db.Column(db.String(50), nullable=False, index=True)
    data_id = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    source_name = db.Column(db.String(200), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    collected_at = db.Column(db.DateTime, nullable=True)
    review_status = db.Column(db.String(50), nullable=False, default=REVIEW_STATUS_PENDING, index=True)
    reviewer_name = db.Column(db.String(200), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("data_type", "data_id", name="uq_review_record_data"),)


class ReviewHistory(db.Model):
    __tablename__ = "review_histories"

    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("review_records.id"), nullable=False, index=True)
    data_type = db.Column(db.String(50), nullable=False, index=True)
    data_id = db.Column(db.Integer, nullable=False, index=True)
    previous_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=False)
    reviewer_name = db.Column(db.String(200), nullable=False)
    review_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    review_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    review_record = db.relationship("ReviewRecord", backref=db.backref("history_entries", cascade="all, delete-orphan"))


class UpdateLog(db.Model):
    __tablename__ = "update_logs"

    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(50), nullable=False, default="news")
    started_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(50), nullable=False, default="success")
    items_found = db.Column(db.Integer, nullable=False, default=0)
    new_items = db.Column(db.Integer, nullable=False, default=0)
    updated_items = db.Column(db.Integer, nullable=False, default=0)
    failed_items = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)
