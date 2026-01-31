import yfinance as yf
import json
import os
import requests
from datetime import datetime, date

# 🔔 Telegram (고정)
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"

STATE_FILE = "portfolio_state.json"

MA_PERIOD = 20          # 20 x 15분봉
INTERVAL = "15m"
PERIOD = "5d"

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    )

def get_15m_prices(ticker):
    hist = yf.download(
        ticker,
        period=PERIOD,
        interval=INTERVAL,
        progress=False
    )

    close = hist["Close"].dropna()

    # ✅ Series / DataFrame 모두 대응 (중요)
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    if len(close) < MA_PERIOD + 2:
        raise ValueError(f"{ticker} 데이터 부족")

    current = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    ma = float(close.iloc[-MA_PERIOD:].mean())

    return current, prev, ma

state = {
    "last_trend": {"SLV": True, "AGQ": True},
    "last_daily_check": ""
}

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state.update(json.load(f))
    except:
        pass

now = datetime.now()
today_str = date.today().isoformat()

alerts = []

for ticker in ["SLV", "AGQ"]:
    price, prev_price, ma = get_15m_prices(ticker)

    in_trend = price >= ma
    was_in_trend = state["last_trend"].get(ticker, True)

    # 🚨 15분봉 추세 이탈 즉시 알림
    if was_in_trend and not in_trend:
        alerts.append(
            f"🚨 {ticker} 15분봉 추세 이탈\n"
            f"현재가: ${price:.2f}\n"
            f"20MA: ${ma:.2f}\n"
            f"시간: {now.strftime('%Y-%m-%d %H:%M')}"
        )

    state["last_trend"][ticker] = in_trend

# 즉시 알림 전송
for msg in alerts:
    send(msg)

# ✅ 하루 1회 정상 작동 확인 알림
if state["last_daily_check"] != today_str:
    lines = []
    for ticker in ["SLV", "AGQ"]:
        status = "상승 추세 유지" if state["last_trend"][ticker] else "추세 이탈 상태"
        lines.append(f"{ticker}: {status}")

    send(
        f"✅ 시스템 정상 작동 확인\n\n"
        f"📅 {now.strftime('%Y-%m-%d %H:%M')}\n"
        + "\n".join(lines)
    )

    state["last_daily_check"] = today_str

with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
