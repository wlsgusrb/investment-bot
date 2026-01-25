import yfinance as yf
import json
import os
import requests
from datetime import datetime

# ======================
# 텔레그램 설정
# ======================
BOT_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
CHAT_ID = "-1003476098424"

# ======================
# 기본 설정
# ======================
INITIAL_CASH = 3_000_000
STATE_FILE = "portfolio_state.json"

TICKERS = {
    "SLV": "SLV",
    "AGQ": "AGQ"
}

# ======================
# 텔레그램 전송 함수
# ======================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ======================
# 상태 불러오기 / 초기화
# ======================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {
        "cash": INITIAL_CASH,
        "SLV": 0,
        "AGQ": 0,
        "last_date": None
    }

# ======================
# 가격 데이터
# ======================
prices = {}
for k, ticker in TICKERS.items():
    df = yf.download(ticker, period="30d", progress=False)
    prices[k] = float(df["Close"].iloc[-1])

# ======================
# 단순 전략 (예시)
# - AGQ가 최근 20일 중 최저가 대비 상승 중이면 AGQ
# - 아니면 SLV
# ======================
agq_df = yf.download("AGQ", period="20d", progress=False)
agq_min = float(agq_df["Close"].min())
agq_now = prices["AGQ"]

if agq_now > agq_min * 1.05:
    target = "AGQ"
else:
    target = "SLV"

# ======================
# 전액 투자 (단순화)
# ======================
total_value = (
    state["cash"]
    + state["SLV"] * prices["SLV"]
    + state["AGQ"] * prices["AGQ"]
)

state["cash"] = 0
state["SLV"] = 0
state["AGQ"] = 0

state[target] = total_value / prices[target]

# ======================
# 상태 저장
# ======================
state["last_date"] = datetime.now().strftime("%Y-%m-%d")

with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)

# ======================
# 메시지 작성
# ======================
msg = f"""
📊 SLV / AGQ 자동 투자 리포트

📅 날짜: {state["last_date"]}

💰 총 자산: {total_value:,.0f} 원

📈 현재가
- SLV: {prices['SLV']:,.2f}
- AGQ: {prices['AGQ']:,.2f}

📌 추천 보유:
- {target} 100%

📦 보유 수량
- SLV: {state['SLV']:.4f}
- AGQ: {state['AGQ']:.4f}
"""

send_telegram(msg)
