import yfinance as yf
import json
import os
import requests
from datetime import datetime, timedelta

# =========================
# 기본 설정
# =========================
START_CAPITAL = 2_000_000  # 시작 자본 200만원
STATE_FILE = "portfolio_state.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ASSETS = ["SLV", "AGQ"]

# =========================
# 가격 조회 함수
# =========================
def get_prices(ticker):
    df = yf.download(ticker, period="40d", progress=False)
    close = df["Close"]

    today = float(close.iloc[-1])
    yesterday = float(close.iloc[-2])
    month_ago = float(close.iloc[-21])

    return today, yesterday, month_ago, close

# =========================
# 상태 불러오기
# =========================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
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
# 판단 로직 (기존 기준 유지)
# =========================
reason = []
weights = state["last_weights"].copy()

# AGQ 추세 판단 (20일 기준)
agq_trend = agq_today / float(agq_series.iloc[-20])

if agq_trend > 1:
    weights = {"SLV": 0.4, "AGQ": 0.4, "CASH": 0.2}
    reason.append("AGQ 중기 추세 유지 → 공격 비중 유지")
else:
    weights = {"SLV": 0.6, "AGQ": 0.0, "CASH": 0.4}
    reason.append("AGQ 추세 이탈 → 레버리지 제거, 방어 전환")

# SLV 방어선 붕괴 체크
slv_trend = slv_today / float(slv_series.iloc[-20])
if slv_trend < 1:
    weights = {"SLV": 0.0, "AGQ": 0.0, "CASH": 1.0}
    reason.append("SLV 중기 추세 붕괴 → 전액 현금")

# =========================
# 변화 여부
# =========================
changed = weights != state["last_weights"]

# =========================
# 메시지 생성 (항상 전송)
# =========================
msg = f"""
📊 Daily Investment Bot

📅 {datetime.now().strftime('%Y-%m-%d')}

[📈 시장 수익률]
SLV
- 일간: {slv_day:.2f}%
- 1개월: {slv_month_r:.2f}%

AGQ
- 일간: {agq_day:.2f}%
- 1개월: {agq_month_r:.2f}%

[📦 추천 비중]
SLV: {weights['SLV']*100:.0f}%
AGQ: {weights['AGQ']*100:.0f}%
현금: {weights['CASH']*100:.0f}%

[🧠 판단 결과]
{" / ".join(reason)}

[🔔 비중 변화]
{"변경 발생" if changed else "변경 없음 (유지)"}
"""

# =========================
# 텔레그램 전송 (무조건)
# =========================
if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    )

# =========================
# 상태 저장
# =========================
state["last_weights"] = weights

with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
