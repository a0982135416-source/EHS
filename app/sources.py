from __future__ import annotations

OFFICIAL_NEWS_SOURCES = [
    {
        "name": "勞動部全球資訊網",
        "source_type": "news",
        "website_url": "https://www.mol.gov.tw/",
        "rss_or_api_url": "https://www.mol.gov.tw/1607/1632/1633/RssList",
        "is_enabled": True,
        "notes": "已實際驗證可使用 RSS feed，僅抓取公開新聞項目，不下載全文。",
        "verification_status": "已驗證",
    },
    {
        "name": "勞動部職業安全衛生署",
        "source_type": "news",
        "website_url": "https://www.osha.gov.tw/",
        "rss_or_api_url": "https://www.osha.gov.tw/48110/48417/48419/RssList",
        "is_enabled": True,
        "notes": "已實際驗證可使用 RSS feed，僅處理標題、摘要、日期與來源網址。",
        "verification_status": "已驗證",
    },
]

OFFICIAL_REGULATION_SOURCES = [
    {
        "name": "勞動部勞動法令查詢系統",
        "source_type": "regulation",
        "website_url": "https://laws.mol.gov.tw/",
        "rss_or_api_url": "https://laws.mol.gov.tw/drafts.aspx?nh=n",
        "is_enabled": True,
        "notes": "已確認可用官方最新動態與法規草案公開頁面，未發現明確 API，但仍屬官方公開介面。",
        "verification_status": "已驗證",
    },
    {
        "name": "全國法規資料庫",
        "source_type": "regulation",
        "website_url": "https://law.moj.gov.tw/",
        "rss_or_api_url": "https://law.moj.gov.tw/News/NewsList.aspx?type=q",
        "is_enabled": True,
        "notes": "已確認官方公開新聞列表頁，可解析法規公告與草案資訊。",
        "verification_status": "已驗證",
    },
    {
        "name": "公共政策網路參與平臺",
        "source_type": "regulation",
        "website_url": "https://join.gov.tw/",
        "rss_or_api_url": "https://join.gov.tw/rss/feed",
        "is_enabled": False,
        "notes": "已確認存在 RSS feed，但內容涵蓋所有公共政策議題，尚未加入篩選職業安全衛生法規草案邏輯。",
        "verification_status": "待篩選",
    },
]
