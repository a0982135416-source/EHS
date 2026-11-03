# 常見錯誤排除

## 1. 模組找不到
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. 資料庫錯誤
確認 `DATABASE_URL` 是否正確，或確認 `site.db` 檔案可寫入。

## 3. 網頁無法開啟
```powershell
.\.venv\Scripts\python.exe run.py
```

若使用 VS Code，確認選擇的是正確的虛擬環境。

## 4. 來源抓取失敗
查看 `/update-logs` 或資料表 `update_logs`，確認錯誤內容。

## 5. Python 版本不相容
本機環境目前驗證成功的版本為 Python 3.14；若使用 3.8，請升級至 3.13 或 3.14。 

## 6. SQLite 無法寫入
確認 site.db 權限與所在資料夾可寫入。

## 7. HTML 模板錯誤
檢查 Jinja2 模板是否引用了不存在的變數，並確認 `context_processor` 已注入。
