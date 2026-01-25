import yfinance as yf
import json
import os
from datetime import datetime
import requests

# ======================
# 텔레그램 설정
# ======================
BOT_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
CHAT_ID = "-1003476098424"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ======================
# 기본 설정
# ======================
START_CAPITAL = 3_000_000
STATE_FILE = "portfolio_state.json"
TICKERS = ["SLV", "AGQ", "SHY"]  # SHY = 현금 대용

# ======================
# 가격 가져오기 (안전 버전)
# ======================
prices = {}

for k in TICKERS:
    df = yf.download(k, period="30d", progress=False)

    if df.empty:
        raise ValueError(f"{k} 가격 데이터 없음")

    close_series = df["Close"]

    # 혹시 DataFrame으로 나올 경우 대비
    if hasattr(close_series, "columns"):
        close_series = close_series.iloc[:, 0]

    price = float(close_series.tail(1).values[0])
    prices[k] = price

# ======================
# 상태 불러오기
# ======================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {
        "date": str(datetime.today().date()),
        "capital": START_CAPITAL,
        "holdings": {
            "SLV": 0,
            "AGQ": 0,
            "SHY": START_CAPITAL
        }
    }

# ======================
# 추천 비중 (예시 로직)
# ======================
weights = {
    "SLV": 0.4,
    "AGQ": 0.4,
    "SHY": 0.2
}

total_capital = sum(state["holdings"].values())

new_holdings = {}
for k in TICKERS:
    new_holdings[k] = round(total_capital * weights[k])

state["holdings"] = new_holdings
state["date"] = str(datetime.today().date())

# ======================
# 상태 저장
# ======================
with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)

# ======================
# 텔레그램 메시지
# ======================
msg = "📊 일일 투자 리포트\n\n"
for k in TICKERS:
    msg += f"{k} 현재가: {prices[k]:,.2f}\n"
    msg += f"{k} 보유금액: {state['holdings'][k]:,}원\n\n"

send_telegram(msg)
