# ================== 기본 설정 ==================
import yfinance as yf
import json
import requests
from datetime import datetime
import os

START_CAPITAL = 2_000_000  # ✅ 시작 자본 200만원
STATE_FILE = "portfolio_state.json"

BOT_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
CHAT_ID = "-1003476098424"

SLV_CORE = 0.30  # SLV 고정 코어

# ================== 텔레그램 ==================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================== 가격 로드 ==================
def get_price(ticker, period="30d"):
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    return float(df["Close"].iloc[-1])

today = datetime.now().strftime("%Y-%m-%d")

slv_price = get_price("SLV")
agq_price = get_price("AGQ")

# ================== 상태 로드 ==================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {
        "base_slv_price": slv_price,
        "base_agq_price": agq_price,
        "date": today
    }

# ================== 추세 판단 ==================
slv_ma200 = yf.download(
    "SLV", period="260d", auto_adjust=True, progress=False
)["Close"].mean()

# ================== 비중 결정 ==================
if slv_price > slv_ma200:
    agq_weight = 0.70
    cash_weight = 0.00
    reason = "SLV가 200일 이동평균 위 → 상승 추세 판단, AGQ 비중 확대"
else:
    agq_weight = 0.20
    cash_weight = 0.50
    reason = "SLV가 200일 이동평균 아래 → 하락/횡보 판단, 현금 비중 확대"

slv_weight = SLV_CORE

# 비중 정합성 보정
total = slv_weight + agq_weight + cash_weight
agq_weight /= total
cash_weight /= total

# ================== 금액 계산 ==================
slv_amt = int(START_CAPITAL * slv_weight)
agq_amt = int(START_CAPITAL * agq_weight)
cash_amt = START_CAPITAL - slv_amt - agq_amt

# ================== 메시지 ==================
message = f"""
📅 기준일: {today}

📈 현재 ETF 가격
SLV : ${slv_price:.2f}
AGQ : ${agq_price:.2f}

🧠 비중 결정 이유
- {reason}

💰 추천 보유 비중 (기준 자본 200만원)
SLV  : {slv_weight*100:.1f}%  → {slv_amt:,}원
AGQ  : {agq_weight*100:.1f}%  → {agq_amt:,}원
현금 : {cash_weight*100:.1f}%  → {cash_amt:,}원
"""

send_telegram(message.strip())

# ================== 상태 저장 ==================
state["base_slv_price"] = slv_price
state["base_agq_price"] = agq_price
state["date"] = today

with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)

print("✅ 실행 완료")
