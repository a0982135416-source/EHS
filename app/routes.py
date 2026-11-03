from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import wraps

import pandas as pd
import plotly.express as px
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.security import safe_join

from .forms import LoginForm, ReviewDecisionForm, UserForm
from .models import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_REJECTED,
    REVIEW_STATUS_REVISION_REQUIRED,
    NewsArticle,
    Regulation,
    RegulationChange,
    RegulationVersion,
    ReviewHistory,
    ReviewRecord,
    UpdateLog,
    User,
    db,
)

main_bp = Blueprint("main", __name__)


def reviewer_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role not in {"reviewer", "admin"}:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _get_reviewable_item(data_type, data_id):
    if data_type == "news":
        return NewsArticle.query.get(data_id)
    if data_type == "regulation":
        return Regulation.query.get(data_id)
    if data_type == "regulation_change":
        return RegulationChange.query.get(data_id)
    return None


def _sync_review_record_for_item(item, data_type):
    if data_type == "news":
        title = item.title
        summary = item.summary
        source_name = item.source_name
        source_url = item.source_url
        published_at = item.published_at
        collected_at = item.collected_at
        review_status = item.review_status or item.verification_status or REVIEW_STATUS_PENDING
    elif data_type == "regulation_change":
        title = f"{item.regulation.name}｜{item.article_no or '條文差異'}"
        summary = item.summary or item.difference_marker or item.new_obligations or "條文差異待人工審核"
        source_name = item.regulation.source_name or "官方資料"
        source_url = item.source_url or item.official_url or item.regulation.source_url or item.regulation.official_url
        published_at = item.published_date
        collected_at = item.created_at
        review_status = item.review_status or REVIEW_STATUS_PENDING
    else:
        title = item.name
        summary = item.summary
        source_name = item.source_name
        source_url = item.source_url or item.official_url
        published_at = item.published_date
        collected_at = item.collected_at
        review_status = item.review_status or item.manual_review_status or REVIEW_STATUS_PENDING

    record = ReviewRecord.query.filter_by(data_type=data_type, data_id=item.id).first()
    if record is None:
        record = ReviewRecord(data_type=data_type, data_id=item.id)
    record.title = title
    record.summary = summary
    record.source_name = source_name
    record.source_url = source_url
    record.published_at = published_at
    record.collected_at = collected_at
    record.review_status = review_status
    db.session.add(record)
    db.session.commit()
    return record


def _count_review_status(status):
    return ReviewRecord.query.filter_by(review_status=status).count()


def seed_regulation_versions():
    created = 0
    for regulation in Regulation.query.order_by(Regulation.id.asc()).all():
        if regulation.versions:
            continue
        version = RegulationVersion(
            regulation_id=regulation.id,
            version_label=f"base-{regulation.id}",
            version_date=regulation.published_date or regulation.notice_date or regulation.collected_at,
            status=regulation.status or "待確認",
            body_text=(regulation.summary or regulation.name or ""),
            summary=regulation.summary,
            source_url=regulation.source_url or regulation.official_url,
            official_url=regulation.official_url,
            notes="已依官方蒐集資料建立版本基線，當官方條文版本資料補齊後可再進行差異比對。",
        )
        db.session.add(version)
        created += 1
    if created:
        db.session.commit()
    return created


def generate_regulation_changes_for_regulation(regulation):
    versions = regulation.versions.order_by(RegulationVersion.created_at.asc()).all()
    if len(versions) < 2:
        return 0

    generated = 0
    for previous_version, current_version in zip(versions, versions[1:]):
        before_text = (previous_version.body_text or "").strip()
        after_text = (current_version.body_text or "").strip()
        if not before_text or not after_text or before_text == after_text:
            continue

        before_lines = before_text.splitlines()
        after_lines = after_text.splitlines()
        matcher = SequenceMatcher(None, before_lines, after_lines)
        markers = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            before_chunk = "\n".join(before_lines[i1:i2])
            after_chunk = "\n".join(after_lines[j1:j2])
            markers.append(f"[{tag.upper()}]\n修正前：{before_chunk[:300]}\n修正後：{after_chunk[:300]}")

        if not markers:
            continue

        change_type = "文字調整"
        lower_after = after_text.lower()
        if any(keyword in lower_after for keyword in ["應", "不得", "要求", "義務", "責任", "通報", "檢查"]):
            change_type = "新增義務"
        elif any(keyword in lower_after for keyword in ["刪除", "撤銷", "廢止"]):
            change_type = "刪除條文"

        record = RegulationChange(
            regulation_id=regulation.id,
            from_version_id=previous_version.id,
            to_version_id=current_version.id,
            article_no=current_version.version_label,
            change_type=change_type,
            before_text=before_text[:4000],
            after_text=after_text[:4000],
            difference_marker="\n\n".join(markers[:6]),
            summary=(current_version.summary or current_version.notes or regulation.summary or "已記錄版本差異，待人工審核").strip()[:2000],
            new_obligations="待人工確認：本比對僅基於已蒐集的版本摘要與官方資料，不能直接視為正式法律解釋。",
            workflow_impact="待人工確認：本比對結果僅供審核人員進一步核對官方原始條文與實施流程。",
            review_status=REVIEW_STATUS_PENDING,
            official_url=regulation.official_url,
            source_url=regulation.source_url,
            published_date=regulation.published_date,
            effective_date=regulation.effective_date,
        )
        db.session.add(record)
        db.session.flush()
        _sync_review_record_for_item(record, "regulation_change")
        generated += 1

    if generated:
        db.session.commit()
    return generated


@main_bp.route("/")
def index():
    all_news = NewsArticle.query.order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.collected_at.desc()).limit(6).all()
    all_regulations = Regulation.query.order_by(Regulation.published_date.desc().nullslast(), Regulation.collected_at.desc()).limit(5).all()
    approved_news = NewsArticle.query.filter(NewsArticle.review_status == REVIEW_STATUS_APPROVED).order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.collected_at.desc()).limit(6).all()
    approved_regulations = Regulation.query.filter(Regulation.review_status == REVIEW_STATUS_APPROVED).order_by(Regulation.published_date.desc().nullslast(), Regulation.collected_at.desc()).limit(5).all()

    latest_news = approved_news if approved_news else all_news
    latest_regulations = approved_regulations if approved_regulations else all_regulations

    last_update = UpdateLog.query.order_by(UpdateLog.finished_at.desc().nullslast()).first()
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template(
        "index.html",
        latest_news=latest_news,
        latest_regulations=latest_regulations,
        last_update=last_update,
        today=today,
    )


@main_bp.route("/news")
def news():
    page = request.args.get("page", 1, type=int)
    search = request.args.get("q", "", type=str)
    query = NewsArticle.query.filter(NewsArticle.review_status == REVIEW_STATUS_APPROVED)
    if search:
        query = query.filter(
            or_(
                NewsArticle.title.ilike(f"%{search}%"),
                NewsArticle.summary.ilike(f"%{search}%"),
                NewsArticle.source_name.ilike(f"%{search}%"),
            )
        )
    items = query.order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.id.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template("news.html", items=items, search=search)


@main_bp.route("/regulations")
def regulations():
    page = request.args.get("page", 1, type=int)
    query = Regulation.query.filter(Regulation.review_status == REVIEW_STATUS_APPROVED)
    items = query.order_by(Regulation.published_date.desc().nullslast(), Regulation.id.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template("regulations.html", items=items)


@main_bp.route("/regulations/<int:id>")
def regulation_detail(id):
    regulation = Regulation.query.get_or_404(id)
    if regulation.review_status != REVIEW_STATUS_APPROVED and not current_user.is_authenticated:
        abort(404)
    return render_template("regulation_detail.html", regulation=regulation)


@main_bp.route("/regulation-changes")
def regulation_changes():
    seed_regulation_versions()
    for regulation in Regulation.query.order_by(Regulation.id.asc()).all():
        if RegulationChange.query.filter_by(regulation_id=regulation.id).count() > 0:
            continue
        version_candidates = sorted(
            regulation.versions,
            key=lambda v: (v.created_at or datetime.min.replace(tzinfo=timezone.utc), v.id),
        )
        version = version_candidates[0] if version_candidates else None
        if version is None:
            continue
        record = RegulationChange(
            regulation_id=regulation.id,
            from_version_id=version.id,
            to_version_id=version.id,
            article_no=version.version_label,
            change_type="待判定",
            before_text=(version.body_text or regulation.summary or "尚未提供條文內容").strip()[:4000],
            after_text=(version.body_text or regulation.summary or "尚未提供條文內容").strip()[:4000],
            difference_marker="僅建立版本基線：目前未取得可靠的修正前／修正後條文，系統不作法律效果推論。",
            summary="已建立官方版本基線，待取得可靠條文版本後再行比對，所有自動摘要均標示為待確認。",
            new_obligations="待人工確認：未取得可靠官方修正版本前，不作新增義務判定。",
            workflow_impact="待人工確認：本紀錄僅供版本基線追蹤，不直接代表工作流程變更。",
            review_status=REVIEW_STATUS_PENDING,
            official_url=regulation.official_url,
            source_url=regulation.source_url,
            published_date=regulation.published_date,
            effective_date=regulation.effective_date,
        )
        db.session.add(record)
        db.session.flush()
        _sync_review_record_for_item(record, "regulation_change")
    db.session.commit()

    can_view_all = current_user.is_authenticated and current_user.role in {"reviewer", "admin"}
    query = RegulationChange.query
    if not can_view_all and RegulationChange.query.filter(RegulationChange.review_status == REVIEW_STATUS_APPROVED).count() > 0:
        query = query.filter(RegulationChange.review_status == REVIEW_STATUS_APPROVED)

    recent_regulations = Regulation.query.filter(Regulation.review_status == REVIEW_STATUS_APPROVED).order_by(Regulation.collected_at.desc()).limit(3).all()
    if not recent_regulations:
        recent_regulations = Regulation.query.order_by(Regulation.collected_at.desc()).limit(3).all()

    items = query.order_by(RegulationChange.created_at.desc()).all()
    versions = RegulationVersion.query.order_by(RegulationVersion.created_at.desc()).limit(10).all()
    return render_template(
        "regulation_changes.html",
        recent_regulations=recent_regulations,
        items=items,
        versions=versions,
        version_count=RegulationVersion.query.count(),
        change_count=RegulationChange.query.count(),
        can_view_all=can_view_all,
        pending_count=RegulationChange.query.filter(RegulationChange.review_status == REVIEW_STATUS_PENDING).count(),
        approved_count=RegulationChange.query.filter(RegulationChange.review_status == REVIEW_STATUS_APPROVED).count(),
    )


@main_bp.route("/regulation-changes/generate", methods=["POST"])
@reviewer_required
def generate_regulation_changes():
    total = 0
    for regulation in Regulation.query.order_by(Regulation.id.asc()).all():
        total += generate_regulation_changes_for_regulation(regulation)
    if total:
        flash(f"已生成 {total} 筆法規差異紀錄，待人工審核後才可正式納入統計。", "success")
    else:
        flash("目前尚無足夠的版本資料可自動生成條文差異，請先補齊官方條文版本內容。", "info")
    return redirect(url_for("main.regulation_changes"))


@main_bp.route("/statistics")
def statistics():
    all_news = NewsArticle.query.all()
    all_regulations = Regulation.query.all()
    approved_news = NewsArticle.query.filter(NewsArticle.review_status == REVIEW_STATUS_APPROVED).all()
    approved_regulations = Regulation.query.filter(Regulation.review_status == REVIEW_STATUS_APPROVED).all()
    display_news = approved_news if approved_news else all_news
    display_regulations = approved_regulations if approved_regulations else all_regulations

    pending_review = _count_review_status(REVIEW_STATUS_PENDING)
    pending_classification = NewsArticle.query.filter(
        (NewsArticle.industry.is_(None)) | (NewsArticle.industry == "待分類")
    ).count()
    last_update = UpdateLog.query.order_by(UpdateLog.finished_at.desc().nullslast()).first()

    def _month_labels(days=6):
        month_index = pd.date_range(end=pd.Timestamp.utcnow(), periods=days, freq="MS")
        return [d.strftime("%Y-%m") for d in month_index]

    months = _month_labels()
    monthly_news = Counter()
    for article in display_news:
        if article.published_at:
            month_key = article.published_at.strftime("%Y-%m")
            monthly_news[month_key] += 1

    monthly_regulation = Counter()
    for regulation in display_regulations:
        if regulation.published_date:
            month_key = regulation.published_date.strftime("%Y-%m")
            monthly_regulation[month_key] += 1

    accident_counts = Counter()
    for article in display_news:
        if article.accident_type and article.accident_type != "待分類":
            accident_counts[article.accident_type] += 1

    industry_counts = Counter()
    for article in display_news:
        if article.industry and article.industry != "待分類":
            industry_counts[article.industry] += 1

    news_month_df = pd.DataFrame({
        "月份": months,
        "新聞篇數": [monthly_news.get(month, 0) for month in months],
    })
    news_month_chart = px.bar(
        news_month_df,
        x="月份",
        y="新聞篇數",
        labels={"x": "月份", "y": "新聞篇數"},
        color_discrete_sequence=["#111111"],
        title="每月職災新聞數",
    )
    news_month_chart.update_layout(
        template="simple_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=10, t=40, b=40),
        font=dict(family="Microsoft JhengHei, serif", size=13),
        title_x=0.02,
        height=320,
    )
    news_month_chart.update_traces(marker_line_color="#111111", marker_line_width=1)

    regulation_month_df = pd.DataFrame({
        "月份": months,
        "新增法規數": [monthly_regulation.get(month, 0) for month in months],
    })
    regulation_month_chart = px.bar(
        regulation_month_df,
        x="月份",
        y="新增法規數",
        labels={"x": "月份", "y": "新增法規數"},
        color_discrete_sequence=["#7a5e2d"],
        title="每月新增法規數",
    )
    regulation_month_chart.update_layout(
        template="simple_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=10, t=40, b=40),
        font=dict(family="Microsoft JhengHei, serif", size=13),
        title_x=0.02,
        height=320,
    )
    regulation_month_chart.update_traces(marker_line_color="#111111", marker_line_width=1)

    accident_df = pd.DataFrame({
        "事故類型": list(accident_counts.keys()),
        "新聞篇數": list(accident_counts.values()),
    })
    accident_chart = px.bar(
        accident_df,
        x="事故類型",
        y="新聞篇數",
        labels={"x": "事故類型", "y": "新聞篇數"},
        color_discrete_sequence=["#2a2a2a"],
        title="事故類型排行",
    )
    accident_chart.update_layout(
        template="simple_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=30, r=10, t=40, b=40),
        font=dict(family="Microsoft JhengHei, serif", size=13),
        title_x=0.02,
        height=320,
    )
    accident_chart.update_traces(marker_line_color="#111111", marker_line_width=1)

    industry_df = pd.DataFrame({
        "產業別": list(industry_counts.keys()),
        "新聞篇數": list(industry_counts.values()),
    })
    industry_chart = px.pie(
        industry_df,
        names="產業別",
        values="新聞篇數",
        title="產業別分布",
    )
    industry_chart.update_layout(
        template="simple_white",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(family="Microsoft JhengHei, serif", size=13),
        title_x=0.02,
        height=320,
    )

    upcoming_regulations = (
        Regulation.query.filter(
            Regulation.effective_date.isnot(None),
        )
        .order_by(Regulation.effective_date.asc())
        .limit(8)
        .all()
    )

    return render_template(
        "statistics.html",
        news_total=len(display_news),
        regulations_total=len(display_regulations),
        pending_review=pending_review,
        pending_classification=pending_classification,
        last_update=last_update,
        news_month_chart=news_month_chart.to_json(),
        regulation_month_chart=regulation_month_chart.to_json(),
        accident_chart=accident_chart.to_json(),
        industry_chart=industry_chart.to_json(),
        upcoming_regulations=upcoming_regulations,
    )


@main_bp.route("/update-logs")
def update_logs():
    page = request.args.get("page", 1, type=int)
    items = UpdateLog.query.order_by(UpdateLog.started_at.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template("update_logs.html", items=items)


@main_bp.route("/health")
def health():
    return {"status": "ok", "database": "ready"}, 200


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.review_dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash("帳號或密碼錯誤。", "error")
            return render_template("login.html", form=form)

        now = datetime.utcnow()
        if user.locked_until and user.locked_until > now:
            flash(f"此帳號暫時鎖定，請稍後再試。", "error")
            return render_template("login.html", form=form)

        if user.check_password(form.password.data):
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = now
            db.session.commit()
            login_user(user)
            next_path = request.args.get("next")
            return redirect(next_path or url_for("main.review_dashboard"))

        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now.replace(microsecond=0)
            user.locked_until = user.locked_until.replace(second=min(user.locked_until.second, 59))
            db.session.commit()
            flash("登入失敗次數過多，帳號已暫時鎖定 10 分鐘。", "error")
        else:
            db.session.commit()
            flash(f"帳號或密碼錯誤，還剩 {5 - user.failed_login_attempts} 次機會。", "error")
        return render_template("login.html", form=form)

    return render_template("login.html", form=form)


@main_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已登出。", "info")
    return redirect(url_for("main.index"))


@main_bp.route("/review")
@reviewer_required
def review_dashboard():
    pending = _count_review_status(REVIEW_STATUS_PENDING)
    approved = _count_review_status(REVIEW_STATUS_APPROVED)
    revision = _count_review_status(REVIEW_STATUS_REVISION_REQUIRED)
    rejected = _count_review_status(REVIEW_STATUS_REJECTED)
    today = datetime.utcnow().date()
    today_count = ReviewRecord.query.filter(db.func.date(ReviewRecord.created_at) == today).count()
    unfinished = ReviewRecord.query.filter(ReviewRecord.review_status.in_([REVIEW_STATUS_PENDING, REVIEW_STATUS_REVISION_REQUIRED])).count()
    recent_records = ReviewRecord.query.order_by(ReviewRecord.updated_at.desc()).limit(5).all()
    return render_template(
        "review_dashboard.html",
        pending_count=pending,
        approved_count=approved,
        revision_count=revision,
        rejected_count=rejected,
        today_count=today_count,
        unfinished_count=unfinished,
        recent_records=recent_records,
    )


@main_bp.route("/review/list")
@reviewer_required
def review_list():
    page = request.args.get("page", 1, type=int)
    data_type = request.args.get("data_type", "")
    status = request.args.get("status", "")
    reviewer_name = request.args.get("reviewer_name", "")
    keyword = request.args.get("q", "")
    source_name = request.args.get("source_name", "")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = ReviewRecord.query
    if data_type:
        query = query.filter(ReviewRecord.data_type == data_type)
    if status:
        query = query.filter(ReviewRecord.review_status == status)
    if reviewer_name:
        query = query.filter(ReviewRecord.reviewer_name.ilike(f"%{reviewer_name}%"))
    if source_name:
        query = query.filter(ReviewRecord.source_name.ilike(f"%{source_name}%"))
    if keyword:
        query = query.filter(or_(ReviewRecord.title.ilike(f"%{keyword}%"), ReviewRecord.summary.ilike(f"%{keyword}%")))
    if start_date:
        query = query.filter(ReviewRecord.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(ReviewRecord.created_at <= datetime.strptime(end_date, "%Y-%m-%d"))

    items = query.order_by(ReviewRecord.updated_at.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template(
        "review_list.html",
        items=items,
        data_type=data_type,
        status=status,
        reviewer_name=reviewer_name,
        keyword=keyword,
        source_name=source_name,
        start_date=start_date,
        end_date=end_date,
    )


@main_bp.route("/review/<int:review_id>")
@reviewer_required
def review_detail(review_id):
    review = ReviewRecord.query.get_or_404(review_id)
    related_item = _get_reviewable_item(review.data_type, review.data_id)
    form = ReviewDecisionForm(reviewer_name=review.reviewer_name or current_user.full_name)
    history_entries = review.history_entries.order_by(ReviewHistory.review_time.desc()).all()
    return render_template("review_detail.html", review=review, related_item=related_item, form=form, history_entries=history_entries)


@main_bp.route("/review/<int:review_id>/process", methods=["POST"])
@reviewer_required
def review_process(review_id):
    review = ReviewRecord.query.get_or_404(review_id)
    action = request.form.get("action")
    if action not in {"approve", "revision", "reject"}:
        flash("請選擇有效的審核操作。", "error")
        return redirect(url_for("main.review_detail", review_id=review.id))

    reviewer_name = (request.form.get("reviewer_name") or current_user.full_name or current_user.username).strip()
    review_note = request.form.get("review_note", "").strip()

    if not reviewer_name:
        flash("請填寫審核人員姓名。", "error")
        return redirect(url_for("main.review_detail", review_id=review.id))

    if action in {"revision", "reject"} and not review_note:
        flash("待修正或不通過時，請填寫理由。", "error")
        return redirect(url_for("main.review_detail", review_id=review.id))

    status_map = {
        "approve": REVIEW_STATUS_APPROVED,
        "revision": REVIEW_STATUS_REVISION_REQUIRED,
        "reject": REVIEW_STATUS_REJECTED,
    }
    new_status = status_map[action]
    previous_status = review.review_status

    item = _get_reviewable_item(review.data_type, review.data_id)
    if item is not None:
        if review.data_type == "news":
            item.review_status = new_status
            item.verification_status = new_status
        elif review.data_type == "regulation":
            item.review_status = new_status
            item.manual_review_status = new_status
        elif review.data_type == "regulation_change":
            item.review_status = new_status

    review.review_status = new_status
    review.reviewer_name = reviewer_name
    review.reviewed_at = datetime.utcnow()
    review.review_note = review_note
    db.session.add(review)

    history = ReviewHistory(
        review_id=review.id,
        data_type=review.data_type,
        data_id=review.data_id,
        previous_status=previous_status,
        new_status=new_status,
        reviewer_name=reviewer_name,
        review_time=datetime.utcnow(),
        review_note=review_note,
    )
    db.session.add(history)
    db.session.commit()

    flash("審核已記錄。", "success")
    return redirect(url_for("main.review_detail", review_id=review.id))


@main_bp.route("/review/history")
@reviewer_required
def review_history():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    reviewer_name = request.args.get("reviewer_name", "")
    data_type = request.args.get("data_type", "")
    query = ReviewHistory.query
    if status:
        query = query.filter(ReviewHistory.new_status == status)
    if reviewer_name:
        query = query.filter(ReviewHistory.reviewer_name.ilike(f"%{reviewer_name}%"))
    if data_type:
        query = query.filter(ReviewHistory.data_type == data_type)

    items = query.order_by(ReviewHistory.review_time.desc()).paginate(page=page, per_page=10, error_out=False)
    return render_template("review_history.html", items=items, status=status, reviewer_name=reviewer_name, data_type=data_type)


@main_bp.route("/review/users")
@admin_required
def review_users():
    users = User.query.order_by(User.created_at.desc()).all()
    form = UserForm()
    return render_template("review_users.html", users=users, form=form)


@main_bp.route("/review/users/create", methods=["POST"])
@admin_required
def create_user():
    form = UserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first():
            flash("帳號已存在。", "error")
            return redirect(url_for("main.review_users"))
        user = User(
            username=username,
            full_name=form.full_name.data.strip(),
            role=(form.role.data or "reviewer").strip() or "reviewer",
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("新審核帳號已建立。", "success")
    return redirect(url_for("main.review_users"))


@main_bp.route("/review/seed")
@admin_required
def seed_review_data():
    for article in NewsArticle.query.all():
        _sync_review_record_for_item(article, "news")
    for regulation in Regulation.query.all():
        _sync_review_record_for_item(regulation, "regulation")
    for change in RegulationChange.query.all():
        _sync_review_record_for_item(change, "regulation_change")
    flash("審核紀錄已同步。", "success")
    return redirect(url_for("main.review_dashboard"))
