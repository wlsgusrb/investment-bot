import yfinance as yf
import json
import os
import requests
from datetime import datetime

# =========================
# 🔐 텔레그램 (사용자 제공)
# =========================
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"

# =========================
# 기본 설정
# =========================
START_CAPITAL = 2_000_000
STATE_FILE = "portfolio_state.json"

# =========================
# 가격 조회 (Series 오류 방지)
# =========================
def get_prices(ticker):
    df = yf.download(ticker, period="40d", progress=False)
    close = df["Close"].dropna().values

    today = float(close[-1])
    yesterday = float(close[-2])
    month_ago = float(close[-21])

    return today, yesterday, month_ago, close

# =========================
# 상태 불러오기
# =========================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
else:
    state = {
        "last_weights": {"SLV": 0.4, "AGQ": 0.4, "CASH": 0.2},
        "last_value": START_CAPITAL
    }

# =========================
# 가격 수집
# =========================
slv_today, slv_yest, slv_month, slv_series = get_prices("SLV")
agq_today, agq_yest, agq_month, agq_series = get_prices("AGQ")

# =========================
# 수익률 계산
# =========================
slv_day = (slv_today / slv_yest - 1) * 100
agq_day = (agq_today / agq_yest - 1) * 100

slv_month_r = (slv_today / slv_month - 1) * 100
agq_month_r = (agq_today / agq_month - 1) * 100

# =========================
# 판단 로직 (백테스트 기준 유지)
# =========================
reason = []
weights = state["last_weights"].copy()

# AGQ 중기 추세 판단
if agq_today / agq_series[-20] > 1:
    weights = {"SLV": 0.4, "AGQ": 0.4, "CASH": 0.2}
    reason.append("AGQ 중기 상승 추세 유지")
else:
    weights = {"SLV": 0.6, "AGQ": 0.0, "CASH": 0.4}
    reason.append("AGQ 중기 추세 이탈")

# SLV 중기 추세 붕괴 시 전량 현금
if slv_today / slv_series[-20] < 1:
    weights = {"SLV": 0.0, "AGQ": 0.0, "CASH": 1.0}
    reason.append("SLV 중기 추세 붕괴 → 전량 현금")

changed = weights != state["last_weights"]

# =========================
# 메시지 (변화 없어도 매일 전송)
# =========================
message = f"""
📊 Daily Investment Bot

📅 {datetime.now().strftime('%Y-%m-%d')}

[📈 오늘 변동]
SLV: {slv_day:.2f}%
AGQ: {agq_day:.2f}%

[📆 최근 1개월]
SLV: {slv_month_r:.2f}%
AGQ: {agq_month_r:.2f}%

[📦 추천 비중]
SLV {weights['SLV']*100:.0f}% |
AGQ {weights['AGQ']*100:.0f}% |
현금 {weights['CASH']*100:.0f}%

[🧠 판단 근거]
{" / ".join(reason)}

[🔔 비중 변화]
{"변경 있음" if changed else "변경 없음 (알림은 매일 전송)"}
"""

# =========================
# 텔레그램 전송
# =========================
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
)

# =========================
# 상태 저장
# =========================
state["last_weights"] = weights
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
