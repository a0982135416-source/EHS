# 系統架構說明

## 1. 網站層
- Flask 應用負責 HTTP 請求、模板渲染與路由管理
- Jinja2 模板負責顯示中文報紙風格頁面
- CSS 提供雜誌/報紙的紙質感與響應式版面

## 2. 業務層
- app/routes.py 處理首頁、新聞、法規、更新紀錄與統計頁面
- app/utils.py 提供資料驗證、更新日誌與差異比對基礎工具
- app/collectors.py 負責 RSS / API 解析入口

## 3. 資料層
- app/models.py 包含 news_articles、regulations、update_logs、data_sources 等表
- SQLite 為初期資料庫，後續可使用 PostgreSQL

## 4. 資料來源層
- app/sources.py 保存官方來源設定
- 每個來源都獨立記錄，並保持 `待驗證` / `已成功` / `已失敗` 狀態

## 5. 更新流程
1. 讀取來源設定
2. 檢查來源是否啟用
3. 取得新資料
4. 進行資料清理與去重
5. 寫入資料庫
6. 紀錄 update_logs
7. 記錄 DataSource 狀態

## 6. 擴充方向
- 加入法規版本比較與人工審核
- 匯入更多官方 RSS / API
- 建立事故事件合併演算法
- 加入 Plotly 統計圖表
- 整合 Windows 工作排程器自動更新
