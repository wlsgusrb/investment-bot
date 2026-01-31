import yfinance as yf
import json
import os
import requests
from datetime import datetime, date

# 🔔 Telegram
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"

STATE_FILE = "portfolio_state.json"

# 전략 설정
MA_PERIOD = 20          # 20 x 15분봉
INTERVAL = "15m"
PERIOD = "5d"

# 현재 보유 비중 (고정)
WEIGHTS = {
    "SLV": 0.4,
    "AGQ": 0.4,
    "CASH": 0.2
}

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

    # Series / DataFrame 대응
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]

    if len(close) < MA_PERIOD + 2:
        raise ValueError(f"{ticker} 데이터 부족")

    current = float(close.iloc[-1])
    ma = float(close.iloc[-MA_PERIOD:].mean())
    day_return = (current / float(close.iloc[-MA_PERIOD]) - 1) * 100

    return current, ma, day_return

state = {
    "last_trend": {"SLV": None, "AGQ": None},
    "last_daily_report": ""
}

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state.update(json.load(f))
    except:
        pass

now = datetime.now()
today_str = date.today().isoformat()

daily_lines = []
trend_alerts = []

for ticker in ["SLV", "AGQ"]:
    price, ma, ret = get_15m_prices(ticker)

    in_trend = price >= ma
    prev_trend = state["last_trend"].get(ticker)

    # 🔔 추세 변화 알림 (변할 때만)
    if prev_trend is not None and prev_trend != in_trend:
        status = "상승 추세 진입" if in_trend else "추세 이탈"
        trend_alerts.append(
            f"🚨 {ticker} 15분봉 추세 변화\n"
            f"상태: {status}\n"
            f"현재가: ${price:.2f}\n"
            f"20MA: ${ma:.2f}\n"
            f"시간: {now.strftime('%Y-%m-%d %H:%M')}"
        )

    state["last_trend"][ticker] = in_trend

    trend_text = "상승 추세" if in_trend else "추세 이탈"
    daily_lines.append(
        f"{ticker}\n"
        f"- 현재가: ${price:.2f}\n"
        f"- 보유 비중: {WEIGHTS[ticker]*100:.0f}%\n"
        f"- 상승률: {ret:.2f}%\n"
        f"- 상태: {trend_text}"
    )

# 📣 추세 변화 알림
for msg in trend_alerts:
    send(msg)

# ✅ 하루 1회 종합 리포트
if state["last_daily_report"] != today_str:
    send(
        f"📊 Daily Silver Portfolio Report\n\n"
        f"📅 {now.strftime('%Y-%m-%d %H:%M')}\n\n"
        + "\n\n".join(daily_lines)
    )
    state["last_daily_report"] = today_str

with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)
