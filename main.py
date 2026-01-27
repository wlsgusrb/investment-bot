import yfinance as yf
import json
import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"

START_CAPITAL = 2_000_000
STATE_FILE = "portfolio_state.json"

def get_prices(ticker):
    t = yf.Ticker(ticker)
    info = t.info

    today = info.get("regularMarketPrice")
    if today is None:
        today = info.get("previousClose")
    today = float(today)

    hist = yf.download(
        ticker,
        period="40d",
        interval="1d",
        progress=False
    )

    close = hist["Close"].dropna().values

    # ✅ 최소 수정 (타입 보정)
    yesterday = float(close[-2].item())
    month_ago = float(close[-21].item())

    return today, yesterday, month_ago, close

state = {
    "last_weights": {"SLV": 0.4, "AGQ": 0.4, "CASH": 0.2},
    "last_value": START_CAPITAL
}

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state.update(json.load(f))
    except:
        pass

slv_today, slv_yest, slv_month, slv_series = get_prices("SLV")
agq_today, agq_yest, agq_month, agq_series = get_prices("AGQ")

slv_day = (slv_today / slv_yest - 1) * 100
agq_day = (agq_today / agq_yest - 1) * 100

slv_month_r = (slv_today / slv_month - 1) * 100
agq_month_r = (agq_today / agq_month - 1) * 100

weights = state["last_weights"].copy()
reason = []

if agq_today / agq_series[-20] > 1:
    weights = {"SLV": 0.4, "AGQ": 0.4, "CASH": 0.2}
    reason.append("AGQ 중기 상승 추세 유지")
else:
    weights = {"SLV": 0.6, "AGQ": 0.0, "CASH": 0.4}
    reason.append("AGQ 중기 추세 이탈")

if slv_today / slv_series[-20] < 1:
    weights = {"SLV": 0.0, "AGQ": 0.0, "CASH": 1.0}
    reason.append("SLV 중기 추세 붕괴 → 현금 전환")

message = f"""
📊 Daily Silver Strategy

📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

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
SLV {weights['SLV']*100:.0f}%
AGQ {weights['AGQ']*100:.0f}%
현금 {weights['CASH']*100:.0f}%

[🧠 판단 근거]
{" / ".join(reason)}
"""

requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    data={"chat_id": TELEGRAM_CHAT_ID, "text": message}
)

state["last_weights"] = weights
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
