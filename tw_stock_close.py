"""台股收盤資料匯出：上市／上櫃／興櫃 → tw_stock_close_YYYYMMDD.xlsx，並以 Gmail 寄出
需求：pip install requests pandas openpyxl
環境變數：
  GMAIL_USER          寄件 Gmail 帳號
  GMAIL_APP_PASSWORD  Gmail 應用程式密碼（16 碼，非登入密碼）
  MAIL_TO             收件人，多位用逗號分隔
  WAIT_MINUTES        資料不是今天時最多等幾分鐘再重抓（預設 30）
  未設定 GMAIL_USER 時只產生檔案、不寄信。
"""
import csv, io, json, os, re, smtplib, sys, time
from email.message import EmailMessage
import requests, pandas as pd
from openpyxl.utils import get_column_letter

TWSE_OPEN = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_RWD = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL?response=json"
OTC = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
ESB = "https://www.tpex.org.tw/openapi/v1/tpex_esb_latest_statistics"

def get(url, parse_json=True):
    last = None
    for n in range(5):  # 最多 5 次；櫃買大檔偶爾傳輸中斷
        try:
            r = requests.get(url, timeout=30); r.raise_for_status()
            return r.json() if parse_json else r.content.decode("utf-8-sig")
        except Exception as e:
            last = e; time.sleep(3 * (n + 1))
    raise RuntimeError(f"{url} 失敗：{last}")

roc = lambda s: f"{int(str(s)[:-4]) + 1911}-{str(s)[-4:-2]}-{str(s)[-2:]}"

def num(v):
    s = str(v).replace(",", "").strip()
    if s in ("", "--", "---", "----", "None"): return None
    try: return float(s)
    except ValueError: return s

TWSE_MAP = {"Date":"資料日期","Code":"證券代號","Name":"證券名稱","OpeningPrice":"開盤價","HighestPrice":"最高價","LowestPrice":"最低價","ClosingPrice":"收盤價","Change":"漲跌","TradeVolume":"成交股數","TradeValue":"成交金額","Transaction":"成交筆數"}
OTC_MAP = {"Date":"資料日期","SecuritiesCompanyCode":"證券代號","CompanyName":"證券名稱","Close":"收盤價","Change":"漲跌","Open":"開盤價","High":"最高價","Low":"最低價","Average":"均價","TradingShares":"成交股數","TransactionAmount":"成交金額","TransactionNumber":"成交筆數","LatestBidPrice":"最後買價","LatesAskPrice":"最後賣價","Capitals":"發行股數","NextReferencePrice":"次日參考價","NextLimitUp":"次日漲停價","NextLimitDown":"次日跌停價"}
ESB_MAP = {"Date":"資料日期","Time":"資料時間","SecuritiesCompanyCode":"證券代號","CompanyName":"證券名稱","PreviousAveragePrice":"前日均價","BuyingPrice":"最高買進價","BuyingQuantity":"最高買進量","SellingPrice":"最低賣出價","SellingQuantity":"最低賣出量","Highest":"最高價","Lowest":"最低價","Average":"日均價","LatestPrice":"最後成交價","Buy/Sell":"買賣別","SuspendTime":"暫停交易時間","TransactionVolume":"成交量","ApplyingDate":"申請上櫃日期","ApplyingStatus":"申請上櫃狀態"}
TEXT = {"資料日期","證券代號","證券名稱","資料時間","買賣別","暫停交易時間","申請上櫃日期","申請上櫃狀態"}

def twse():
    # OpenAPI 有時落後一天；與 rwd 版比較，取日期較新者
    a = pd.DataFrame(get(TWSE_OPEN)).rename(columns=TWSE_MAP)
    try:
        rows = [r for r in csv.reader(io.StringIO(get(TWSE_RWD, False))) if r]
        b = pd.DataFrame([r for r in rows[1:] if len(r) == len(rows[0]) and re.fullmatch(r"\d{7}", r[0])], columns=rows[0])
        b = b.rename(columns={"日期":"資料日期","漲跌價差":"漲跌"})[list(TWSE_MAP.values())]
        if b["資料日期"].max() > a["資料日期"].max(): return b
    except Exception as e:
        print("rwd 備援失敗：", e, file=sys.stderr)
    return a

def clean(df):
    df = df.copy(); df["資料日期"] = df["資料日期"].map(roc)
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip() if c in TEXT else df[c].map(num)
    cols = ["資料日期"] + [c for c in df.columns if c != "資料日期"]
    return df[cols].sort_values("證券代號", key=lambda s: s.astype(str)).reset_index(drop=True)

def fetch_all():
    return {"上市": clean(twse()),
            "上櫃": clean(pd.DataFrame(get(OTC)).rename(columns=OTC_MAP)),
            "興櫃": clean(pd.DataFrame(get(ESB)).rename(columns=ESB_MAP))}

def write_xlsx(sheets, fn):
    with pd.ExcelWriter(fn, engine="openpyxl") as w:
        for k, df in sheets.items():
            df.to_excel(w, sheet_name=k, index=False)
            ws = w.sheets[k]; ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
            for i, c in enumerate(df.columns, 1):
                L = max([len(c) * 2] + [sum(2 if ord(ch) > 127 else 1 for ch in str(x)) for x in df[c].head(300)])
                ws.column_dimensions[get_column_letter(i)].width = min(max(L + 2, 8), 30)

def send_mail(subject, body, fn):
    user, pwd, to = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD"), os.getenv("MAIL_TO")
    if not (user and pwd and to):
        print("未設定 GMAIL_USER / GMAIL_APP_PASSWORD / MAIL_TO，略過寄信"); return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(body)
    with open(fn, "rb") as f:
        msg.add_attachment(f.read(), maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=fn)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pwd); s.send_message(msg)
    print("已寄信給", to)

def main():
    today = pd.Timestamp.now(tz="Asia/Taipei").strftime("%Y-%m-%d")
    deadline = time.time() + int(os.getenv("WAIT_MINUTES", "30")) * 60
    while True:
        sheets = fetch_all()
        dates = {k: v["資料日期"].max() for k, v in sheets.items()}
        if all(d == today for d in dates.values()) or time.time() >= deadline:
            break
        print("資料尚未全部更新到今天：", dates, "，5 分鐘後重抓"); time.sleep(300)
    dd = max(dates.values())
    fn = f"tw_stock_close_{dd.replace('-', '')}.xlsx"
    write_xlsx(sheets, fn)
    lines = [f"{k}：{len(v):,} 筆，資料日期 {dates[k]}" for k, v in sheets.items()]
    note = ""
    if all(d != today for d in dates.values()):
        note = f"資料日期為 {dd}，非今日（可能休市或尚未更新）"
    elif any(d != today for d in dates.values()):
        note = "注意：部分市場資料不是今天，請檢查"
    body = "\n".join(([note, ""] if note else []) + ["台股收盤資料（上市／上櫃／興櫃），詳見附件。", ""] + lines)
    print(body)
    send_mail(f"台股收盤資料 {dd}" + ("（非今日資料）" if note.startswith("資料日期") else ""), body, fn)

if __name__ == "__main__":
    main()
