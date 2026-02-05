import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"
STATE_FILE = "portfolio_state.json"

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"메시지 전송 에러: {e}")

def get_realtime_data():
    try:
        # 3번 코드처럼 SLV 데이터를 1시간/15분봉으로 수집
        ticker = "SLV"
        data_1h = yf.download(ticker, period="5d", interval="1h", progress=False)
        data_15m = yf.download(ticker, period="2d", interval="15m", progress=False)
        
        if data_1h.empty or data_15m.empty: raise ValueError("데이터 실패")

        curr_price = float(data_15m['Close'].iloc[-1])
        
        # [3번 코드 기준] 최근 고점 (1시간 봉의 High 값 중 가장 높은 값)
        # 3번 코드에서 의도했던 '최근 고점 대비 하락'을 정확히 구현합니다.
        max_high = float(data_1h['High'].iloc[-1]) 
        
        # 추세 지표 (MA10, RSI)
        close_series = data_1h['Close'].squeeze()
        ma10_1h = float(close_series.rolling(window=10).mean().iloc[-1])
        
        delta = close_series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi_1h = float(100 - (100 / (1 + (gain / loss).iloc[-1])))
        
        return curr_price, ma10_1h, rsi_1h, max_high
    except Exception as e:
        raise e

if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f: state = json.load(f)
    except: state = {"last_guide": "", "last_report_date": ""}
else:
    state = {"last_guide": "", "last_report_date": ""}

now = datetime.now()
today_str = now.strftime('%Y-%m-%d')

try:
    curr_price, ma_1h, rsi_1h, max_high = get_realtime_data()
    drop_from_high = (curr_price / max_high - 1) * 100

    # [3번 코드와 동일한 전략]
    # 1. 폭락 감지 (3번 코드 기준인 -10.0% 또는 설정하신 민감도 적용)
    # 아까 3번 코드 본문에는 -10.0%였으므로 그대로 맞춥니다.
    if drop_from_high <= -10.0:
        tag, guide = "PANIC_EXIT", "🚨 전량 현금화 (폭락 감지)"
    # 2. RSI 단계별 분할 매도
    elif rsi_1h >= 70:
        if rsi_1h >= 85: tag, guide = "SELL_3", "🔥 현금 80%"
        elif rsi_1h >= 80: tag, guide = "SELL_2", "⚖️ 현금 60%"
        else: tag, guide = "SELL_1", "✅ 현금 30%"
    # 3. 이평선 기준 상승/하락 추세
    elif curr_price > ma_1h * 1.005:
        tag = "AGGRESSIVE" if rsi_1h > 65 else "NORMAL"
        guide = "🔥 AGQ 80%" if tag == "AGGRESSIVE" else "📈 AGQ 40%, SLV 40%"
    elif curr_price < ma_1h * 0.995:
        tag = "DEFENSE" if drop_from_high <= -5.0 else "WAIT"
        guide = "🛡️ 현금 80%" if tag == "DEFENSE" else "⚠️ 현금 50%, SLV 40%"
    # 4. 횡보장 (이전 상태 유지)
    else:
        tag = state.get("last_tag", "WAIT")
        guide = state.get("last_guide", "⚠️ 현금 50%, SLV 40%")

    is_guide_changed = (state.get("last_guide") != guide)
    is_daily_report = (state.get("last_report_date") != today_str)

    if is_guide_changed or is_daily_report:
        title = "🔄 [Silver 비중 변동]" if is_guide_changed else "☀️ [정기 보고]"
        msg = f"{title}\n📊 상태: {tag}\n📉 고점대비: {drop_from_high:.2f}%\n👉 행동: {guide}"
        send_msg(msg)
        
        state.update({"last_tag": tag, "last_guide": guide, "last_report_date": today_str})
        with open(STATE_FILE, "w") as f: json.dump(state, f)

except Exception as e:
    send_msg(f"❌ 봇 에러: {str(e)}")
