import yfinance as yf
import json
import os
import requests
from datetime import datetime

# =========================
# 텔레그램 설정 (그대로)
# =========================
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"

# =========================
# 기본 설정 (그대로)
# =========================
START_CAPITAL = 2_000_000
STATE_FILE = "portfolio_state.json"

# =========================
# 가격 조회 (🔥 오류만 최소 수정)
# =========================
def get_prices(ticker):
    df = yf.download(ticker, period="40d", progress=False)

    close = df["Close"].dropna().values

    # 🔧 핵심 수정: .item()으로 스칼라 강제
    today = float(close[-1].item())
    yesterday = float(close[-2].item())
    month_ago = float(close[-21].item())

    return today, yesterday, month_ago, close

# =========================
# 상태 로드 (그대로)
# =========================
state = {
    "last_weights": {"SLV": 0.4, "AGQ": 0.4, "CASH": 0.2},
    "last_value": START_CAPITAL
}

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
            state.update(saved)
    except:
        pass

# =========================
# 가격 수집
# =========================
slv_today, slv_yest, slv_month, slv_series = get_prices("SLV")
agq_today, agq_yest, agq_month, agq_series = get_prices("AGQ")

# =========================
# 수익률 계산 (그대로)
# =========================
slv_day = (slv_today / slv_yest - 1) * 100
agq_day = (agq_today / agq_yest - 1) * 100

slv_month_r = (slv_today / slv_month - 1) * 100
agq_month_r = (agq_today / agq_month - 1) * 100

# =========================
# 비중 판단 로직 (🔥 절대 안 건드림)
# =========================
weights = state["last_weights"].copy()
reason = []

if agq_today / float(agq_series[-20].item()) > 1:
    weights = {"SLV": 0.4, "AGQ": 0.4, "CASH": 0.2}
    reason.append("AGQ 중기 상승 추세 유지")
else:
    weights = {"SLV": 0.6, "AGQ": 0.0, "CASH": 0.4}
    reason.append("AGQ 중기 추세 이탈")

if slv_today / float(slv_series[-20].item()) < 1:
    weights = {"SLV": 0.0, "AGQ": 0.0, "CASH": 1.0}
    reason.append("SLV 중기 추세 붕괴 → 현금 전환")

changed = weights != state["last_weights"]

# =========================
# 금액 계산 (그대로)
# =========================
total = state["last_value"]

slv_amt = total * weights["SLV"]
agq_amt = total * weights["AGQ"]
cash_amt = total * weights["CASH"]

# =========================
# 텔레그램 메시지 (그대로)
# =========================
message = f"""
📊 Daily Silver Strategy

📅 {datetime.now().strftime('%Y-%m-%d')}

[💵 현재가]
SLV: ${slv_today:.2f}
AGQ: ${agq_today:.2f}

[📈 일간 변동]
SLV: {slv_day:.2f}%
AGQ: {agq_day:.2f}%

[📆 1개월 변동]
SLV: {slv_month_r:.2f}%
AGQ: {agq_month_r:.2f}%

[📦 추천 비중]
SLV {weights['SLV']*100:.0f}% ({slv_amt:,.0f}원)
AGQ {weights['AGQ']*100:.0f}% ({agq_amt:,.0f}원)
현금 {weights['CASH']*100:.0f}% ({cash_amt:,.0f}원)

[🧠 판단 근거]
{" / ".join(reason)}

[🔔 비중 변화]
{"변경 있음" if changed else "변경 없음 (매일 알림 전송)"}
"""

# =========================
# 텔레그램 전송 (무조건 매일)
# =========================
requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
)

# =========================
# 상태 저장 (그대로)
# =========================
state["last_weights"] = weights

with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
