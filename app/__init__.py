import os
from datetime import datetime

from flask import Flask, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy import inspect, text

from .config import Config
from .models import NewsArticle, Regulation, RegulationChange, ReviewRecord, User, db
from .utils import sanitize_text

login_manager = LoginManager()
login_manager.login_view = "main.login"
login_manager.login_message = "請先登入後再進行人工審核。"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def ensure_schema_migration():
    with db.engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())

        if "news_articles" in tables:
            news_columns = {col["name"] for col in inspector.get_columns("news_articles")}
            if "review_status" not in news_columns:
                connection.execute(text("ALTER TABLE news_articles ADD COLUMN review_status VARCHAR(50) DEFAULT '待審核'"))
            connection.execute(text("UPDATE news_articles SET review_status = COALESCE(review_status, verification_status, '待審核') WHERE review_status IS NULL OR review_status = ''"))

        if "regulations" in tables:
            regulation_columns = {col["name"] for col in inspector.get_columns("regulations")}
            if "review_status" not in regulation_columns:
                connection.execute(text("ALTER TABLE regulations ADD COLUMN review_status VARCHAR(50) DEFAULT '待審核'"))
            connection.execute(text("UPDATE regulations SET review_status = COALESCE(review_status, manual_review_status, '待審核') WHERE review_status IS NULL OR review_status = ''"))

        if "users" in tables:
            user_columns = {col["name"] for col in inspector.get_columns("users")}
            if "failed_login_attempts" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0 NOT NULL"))
            if "locked_until" not in user_columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN locked_until DATETIME NULL"))


def ensure_default_admin_user():
    username = (os.getenv("ADMIN_USERNAME") or "").strip()
    password = (os.getenv("ADMIN_PASSWORD") or "").strip()
    if not username or not password:
        return None

    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(
            username=username,
            full_name=os.getenv("ADMIN_FULL_NAME", "系統管理者"),
            role="admin",
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    return user


def sync_review_records():
    for article in NewsArticle.query.all():
        article.title = sanitize_text(article.title)
        article.summary = sanitize_text(article.summary)
        article.source_name = sanitize_text(article.source_name)
        if not article.review_status:
            article.review_status = article.verification_status or "待審核"
        article.verification_status = article.review_status or "待審核"

        record = ReviewRecord.query.filter_by(data_type="news", data_id=article.id).first()
        if record is None:
            record = ReviewRecord(data_type="news", data_id=article.id)
        record.title = article.title
        record.summary = article.summary
        record.source_name = article.source_name
        record.source_url = article.source_url
        record.published_at = article.published_at
        record.collected_at = article.collected_at
        record.review_status = article.review_status
        db.session.add(record)

    for regulation in Regulation.query.all():
        regulation.name = sanitize_text(regulation.name)
        regulation.summary = sanitize_text(regulation.summary)
        regulation.authority = sanitize_text(regulation.authority)
        regulation.status = sanitize_text(regulation.status)
        regulation.source_name = sanitize_text(regulation.source_name)
        if not regulation.review_status:
            regulation.review_status = regulation.manual_review_status or "待審核"

        record = ReviewRecord.query.filter_by(data_type="regulation", data_id=regulation.id).first()
        if record is None:
            record = ReviewRecord(data_type="regulation", data_id=regulation.id)
        record.title = regulation.name
        record.summary = regulation.summary
        record.source_name = regulation.source_name
        record.source_url = regulation.source_url or regulation.official_url
        record.published_at = regulation.published_date
        record.collected_at = regulation.collected_at
        record.review_status = regulation.review_status
        db.session.add(record)

    for change in RegulationChange.query.all():
        change.summary = sanitize_text(change.summary)
        change.new_obligations = sanitize_text(change.new_obligations)
        change.workflow_impact = sanitize_text(change.workflow_impact)
        if not change.review_status:
            change.review_status = "待審核"

        record = ReviewRecord.query.filter_by(data_type="regulation_change", data_id=change.id).first()
        if record is None:
            record = ReviewRecord(data_type="regulation_change", data_id=change.id)
        record.title = f"{change.regulation.name}｜{change.article_no or '條文差異'}"
        record.summary = change.summary or change.difference_marker or "條文差異待人工審核"
        record.source_name = change.regulation.source_name or "官方資料"
        record.source_url = change.source_url or change.official_url or change.regulation.source_url or change.regulation.official_url
        record.published_at = change.published_date
        record.collected_at = change.created_at
        record.review_status = change.review_status
        db.session.add(record)

    db.session.commit()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    login_manager.init_app(app)
    Migrate(app, db)

    from .routes import main_bp

    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_common_context():
        now = datetime.now()
        return {
            "datetime_now": now,
            "weekday": ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][now.weekday()],
            "issue_no": now.strftime("%Y%m%d"),
        }

    with app.app_context():
        db.create_all()
        ensure_schema_migration()
        ensure_default_admin_user()
        sync_review_records()

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("500.html"), 500

    return app


app = create_app()
