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
# 📈 가격 데이터 안전하게 가져오기
# ==============================
def get_prices(ticker, days=30):
    df = yf.download(ticker, period=f"{days}d", progress=False)
    close = df["Close"]

    today = close.iloc[-1]
    yesterday = close.iloc[-2]
    month_ago = close.iloc[0]

    for v in [today, yesterday, month_ago]:
        if hasattr(v, "values"):
            v = v.values[0]

    return float(today), float(yesterday), float(month_ago)

# ==============================
# 📊 판단 로직 (백테스트 기준 그대로)
# ==============================
def decide_weights(agq_today, agq_20d_ago):
    ratio = agq_today / agq_20d_ago

    if ratio > 1.0:
        return {
            "SLV": 0.4,
            "AGQ": 0.4,
            "CASH": 0.2,
            "reason": "AGQ가 20일 전 대비 상승 → 상승 추세 유지 판단"
        }
    else:
        return {
            "SLV": 0.6,
            "AGQ": 0.1,
            "CASH": 0.3,
            "reason": "AGQ 약세 → 변동성 회피, 현금 비중 확대"
        }

# ==============================
# 💾 상태 로드 (없으면 자동 복구)
# ==============================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {}

if "last_value" not in state:
    state["last_value"] = START_CAPITAL

if "start_date" not in state:
    state["start_date"] = datetime.today().strftime("%Y-%m-%d")

# ==============================
# 📈 가격 수집
# ==============================
slv_today, slv_yesterday, slv_month = get_prices("SLV")
agq_today, agq_yesterday, agq_month = get_prices("AGQ")

# ==============================
# 📊 등락률 계산
# ==============================
def pct(a, b):
    return (a / b - 1) * 100

slv_day = pct(slv_today, slv_yesterday)
agq_day = pct(agq_today, agq_yesterday)

slv_month_chg = pct(slv_today, slv_month)
agq_month_chg = pct(agq_today, agq_month)

# ==============================
# 🧠 판단
# ==============================
decision = decide_weights(agq_today, agq_month)

# ==============================
# 💰 금액 계산
# ==============================
total_value = state["last_value"]

allocations = {
    "SLV": total_value * decision["SLV"],
    "AGQ": total_value * decision["AGQ"],
    "CASH": total_value * decision["CASH"]
}

cumulative_return = (total_value / START_CAPITAL - 1) * 100

# ==============================
# ✉️ 텔레그램 메시지
# ==============================
message = f"""
📊 은 투자 자동 추천 시스템

📅 날짜: {datetime.today().strftime("%Y-%m-%d")}

💰 현재 평가금액: {total_value:,.0f}원
📈 누적 수익률: {cumulative_return:.2f}%

━━━━━━━━━━━━━━
📌 가격 변화
SLV
- 현재가: ${slv_today:.2f}
- 일간: {slv_day:+.2f}%
- 한달: {slv_month_chg:+.2f}%

AGQ
- 현재가: ${agq_today:.2f}
- 일간: {agq_day:+.2f}%
- 한달: {agq_month_chg:+.2f}%
━━━━━━━━━━━━━━

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
with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)

print("✅ 실행 완료")
