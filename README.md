# daily-fetch：台股收盤資料每日寄送

每個交易日抓取上市（證交所）、上櫃、興櫃（櫃買中心）的收盤資料，整理成 Excel（三個工作表），再用 Gmail 寄出。

## 設定步驟

1. 建立公開 repo `daily-fetch`，放入 `tw_stock_close.py` 和 `.github/workflows/tw_stock_close.yml`。
2. 產生 Gmail 應用程式密碼：Google 帳戶 → 安全性 → 兩步驟驗證（需先開啟）→ 應用程式密碼。
3. 在 repo 的 Settings → Secrets and variables → Actions 新增三個 secret：
   - `GMAIL_USER`：寄件 Gmail
   - `GMAIL_APP_PASSWORD`：上一步的 16 碼密碼
   - `MAIL_TO`：收件人，多位用逗號分隔
4. 到 Actions 頁面手動執行一次（Run workflow）測試。

## 觸發方式

workflow 只有 `workflow_dispatch`，由 cron-job.org 呼叫 GitHub API 觸發。workflow 裡不設 GitHub 內建排程（`schedule`），原因有兩個：負載高時會延遲，排隊的 job 可能被丟掉；公開 repo 60 天沒有活動，排程會被自動停用。

1. 建立 fine-grained token：Repository access 只選 `daily-fetch`，權限 Actions = Read and write。
2. 在 cron-job.org 新增工作：
   - URL：`https://api.github.com/repos/gwpandia/daily-fetch/actions/workflows/tw_stock_close.yml/dispatches`
   - Method：POST
   - Headers：`Authorization: Bearer <token>`、`Accept: application/vnd.github+json`
   - Body：`{"ref":"main"}`
   - 時間：週一到週五 16:25（時區 Asia/Taipei）
3. 在 cron-job.org 開啟這個工作的失敗通知。如果 GitHub 回錯誤（例如 5xx），那天不會寄信；收到通知後，到 Actions 頁面手動執行。
4. 如果 token 設了到期日，到期前產生新 token，並更新 cron-job.org 的 `Authorization` 標頭。

在 Actions 頁面，cron-job.org 觸發和手動觸發的 event 都是 `workflow_dispatch`。要確認是哪一種，對照 cron-job.org 的執行紀錄時間。

## 行為說明

- 如果資料還不是今天，每 5 分鐘重抓一次，最多等 30 分鐘（`WAIT_MINUTES`）；最後仍不是今天就照樣寄出，主旨會標註「非今日資料」（通常是休市）。
- 證交所 OpenAPI 有時會落後一天，程式會自動改用 twse.com.tw 的備援資料。
- 每次執行約 1～2 分鐘；在等資料的日子最多約 35 分鐘。公開 repo 的 Actions 不計分鐘數。
- Excel 也會保留在該次 Actions 執行頁面 7 天，可以下載。
