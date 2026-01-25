import yfinance as yf
import json
import os
from datetime import datetime
import requests

# ==============================
# 🔐 텔레그램 설정
# ==============================
BOT_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
CHAT_ID = "-1003476098424"

# ==============================
# 💰 기본 설정
# ==============================
START_CAPITAL = 2_000_000  # 200만원
STATE_FILE = "portfolio_state.json"

TICKERS = ["SLV", "AGQ"]

# ==============================
# 📈 가격 가져오기 (안 터지는 버전)
# ==============================
def get_price(ticker: str) -> float:
    df = yf.download(ticker, period="10d", progress=False)
    close = df["Close"].iloc[-1]
    if hasattr(close, "values"):
        close = close.values[0]
    return float(close)

# ==============================
# 📊 판단 로직 (백테스트 그대로)
# ==============================
def decide_weights(slv_price, agq_price):
    agq_20d_ago = yf.download("AGQ", period="20d", progress=False)["Close"].iloc[0]
    if hasattr(agq_20d_ago, "values"):
        agq_20d_ago = agq_20d_ago.values[0]

    ratio = agq_price / float(agq_20d_ago)

    if ratio > 1.0:
        # 공격적 국면
        return {
            "SLV": 0.4,
            "AGQ": 0.4,
            "CASH": 0.2,
            "reason": "AGQ가 20일 전 대비 상승 → 추세 유지 판단"
        }
    else:
        # 방어적 국면
        return {
            "SLV": 0.6,
            "AGQ": 0.1,
            "CASH": 0.3,
            "reason": "AGQ 약세 → 변동성 회피"
        }

# ==============================
# 💾 상태 로드 / 저장
# ==============================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {
        "start_date": datetime.today().strftime("%Y-%m-%d"),
        "capital": START_CAPITAL,
        "last_value": START_CAPITAL
    }

# ==============================
# 📈 오늘 가격
# ==============================
prices = {t: get_price(t) for t in TICKERS}

# ==============================
# 🧠 판단
# ==============================
decision = decide_weights(prices["SLV"], prices["AGQ"])

# ==============================
# 💰 금액 계산
# ==============================
total_value = state["last_value"]

allocations = {
    "SLV": total_value * decision["SLV"],
    "AGQ": total_value * decision["AGQ"],
    "CASH": total_value * decision["CASH"]
}

# ==============================
# 📊 누적 수익률
# ==============================
cumulative_return = (total_value / START_CAPITAL - 1) * 100

# ==============================
# ✉️ 텔레그램 메시지
# ==============================
message = f"""
📊 은 투자 자동 추천 시스템

📅 날짜: {datetime.today().strftime("%Y-%m-%d")}

💰 현재 평가금액: {total_value:,.0f}원
📈 누적 수익률: {cumulative_return:.2f}%

🔍 현재가
- SLV: ${prices['SLV']:.2f}
- AGQ: ${prices['AGQ']:.2f}

📌 추천 비중
- SLV: {decision['SLV']*100:.0f}% → {allocations['SLV']:,.0f}원
- AGQ: {decision['AGQ']*100:.0f}% → {allocations['AGQ']:,.0f}원
- 현금: {decision['CASH']*100:.0f}% → {allocations['CASH']:,.0f}원

🧠 판단 이유
- {decision['reason']}
"""

requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": message}
)

# ==============================
# 💾 상태 저장
# ==============================
state["last_value"] = total_value

with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)

print("✅ 실행 완료")
