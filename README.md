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

## 觸發方式（擇一）

- **A. GitHub 排程**：workflow 預設 UTC 08:37（台北 16:37）。可能延遲 5～30 分鐘；repo 連續 60 天沒有任何 commit，GitHub 會自動停用排程。
- **B. cron-job.org（較準時）**：刪掉 yml 裡的 `schedule:` 兩行，然後：
  1. 建立 fine-grained token：只選這個 repo，權限 Actions = Read and write。
  2. 在 cron-job.org 新增工作：
     - URL：`https://api.github.com/repos/<你的帳號>/daily-fetch/actions/workflows/tw_stock_close.yml/dispatches`
     - Method：POST
     - Headers：`Authorization: Bearer <token>`、`Accept: application/vnd.github+json`
     - Body：`{"ref":"main"}`
     - 時間：週一到週五 16:25（時區 Asia/Taipei）
  - 用這種方式觸發，不受 60 天停用的限制。

## 行為說明

- 如果資料還不是今天，每 5 分鐘重抓一次，最多等 30 分鐘（`WAIT_MINUTES`）；最後仍不是今天就照樣寄出，主旨會標註「非今日資料」（通常是休市）。
- 證交所 OpenAPI 有時會落後一天，程式會自動改用 twse.com.tw 的備援資料。
- 每次執行約 1～2 分鐘；在等資料的日子最多約 35 分鐘。公開 repo 的 Actions 不計分鐘數。
- Excel 也會保留在該次 Actions 執行頁面 7 天，可以下載。
