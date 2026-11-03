from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REQUEST_TIMEOUT = 20
REQUESTS_VERIFY_SSL = os.getenv("REQUESTS_VERIFY_SSL", "false").strip().lower() not in {"0", "false", "no"}

MOL_DRAFT_URL = "https://laws.mol.gov.tw/drafts.aspx?nh=n"
MOJ_NEWS_URL = "https://law.moj.gov.tw/News/NewsList.aspx?type=q"


def _safe_get(url: str) -> requests.Response:
    return requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0"},
        verify=REQUESTS_VERIFY_SSL,
    )


def _taiwan_date_to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    clean = value.strip().replace("民國", "").replace("年", "-").replace("月", "-").replace("日", "")
    clean = re.sub(r"\s+", "", clean)
    try:
        year_str, month_str, day_str = clean.split("-")
        year = int(year_str) + 1911
        return datetime(year, int(month_str), int(day_str))
    except Exception:
        return None


def fetch_mol_law_news() -> list[dict[str, Any]]:
    response = _safe_get(MOL_DRAFT_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    items: list[dict[str, Any]] = []
    rows = soup.select("table tr, .news-item, .news-list")
    for row in rows:
        text = " ".join(row.get_text(" ", strip=True).split())
        if not text:
            continue
        if "法規草案" not in text and "公告" not in text and "勞動部" not in text:
            continue
        anchors = row.find_all("a")
        if not anchors:
            continue
        link = anchors[0].get("href")
        title = anchors[0].get_text(" ", strip=True)
        if not title:
            continue
        if link and not link.startswith("http"):
            link = "https://laws.mol.gov.tw/" + link.lstrip("/")
        items.append(
            {
                "name": title,
                "authority": "勞動部",
                "source_name": "勞動部勞動法令查詢系統",
                "source_url": link or "https://laws.mol.gov.tw/",
                "status": "草案預告中" if "預告" in title else "待確認",
                "published_date": None,
                "summary": text,
                "official_url": link or "https://laws.mol.gov.tw/",
            }
        )
    return items


def fetch_moj_news() -> list[dict[str, Any]]:
    response = _safe_get(MOJ_NEWS_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    items: list[dict[str, Any]] = []
    for row in soup.select("a"):
        title = row.get_text(" ", strip=True)
        href = row.get("href")
        if not title or not href:
            continue
        if not any(keyword in title for keyword in ["法規", "公告", "草案", "修正", "命令", "行政規則"]):
            continue
        full_url = href if href.startswith("http") else "https://law.moj.gov.tw/" + href.lstrip("/")
        items.append(
            {
                "name": title,
                "authority": "法務部/主管機關",
                "source_name": "全國法規資料庫",
                "source_url": full_url,
                "status": "草案預告中" if "預告" in title else "待確認",
                "published_date": None,
                "summary": title,
                "official_url": full_url,
            }
        )
    return items
