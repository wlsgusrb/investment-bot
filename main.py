import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
import time
from datetime import datetime

warnings.filterwarnings('ignore')

# [유지] 사용자님 설정값
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"
STATE_FILE = "portfolio_state.json"

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"메시지 전송 에러: {e}")

def get_hybrid_data():
    for i in range(3):
        try:
            slv_1h = yf.download("SLV", period="5d", interval="1h", progress=False)
            slv_15m = yf.download("SLV", period="2d", interval="15m", progress=False)
            agq_15m = yf.download("AGQ", period="2d", interval="15m", progress=False)
            if slv_1h.empty or slv_15m.empty: raise ValueError("데이터 실패")
            
            curr_slv = slv_15m['Close'].dropna().iloc[-1]
            ma10_1h = slv_1h['Close'].rolling(window=10).mean().dropna().iloc[-1]
            max_high_recent = float(slv_1h['High'].iloc[-1])

            delta = slv_1h['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_1h = (100 - (100 / (1 + (gain / loss)))).dropna().iloc[-1]
            
            return curr_slv, ma10_1h, rsi_1h, max_high_recent
        except Exception as e:
            if i < 2: time.sleep(5); continue
            else: raise e

# 상태 로드
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f: state = json.load(f)
    except: state = {"last_guide": "", "last_report_date": ""}
else:
    state = {"last_guide": "", "last_report_date": ""}

now = datetime.now()
today_str = now.strftime('%Y-%m-%d')

try:
    curr_slv, ma_1h, rsi_1h, max_high = get_hybrid_data()
    drop_from_high = (curr_slv / max_high - 1) * 100

    # 로직 판단
    if drop_from_high <= -10.0:
        tag, guide = "PANIC_EXIT", "🚨 전량 현금화"
    elif rsi_1h >= 70:
        if rsi_1h >= 85: tag, guide = "SELL_3", "🔥 현금 80%"
        elif rsi_1h >= 80: tag, guide = "SELL_2", "⚖️ 현금 60%"
        else: tag, guide = "SELL_1", "✅ 현금 30%"
    elif curr_slv > ma_1h * 1.005:
        tag = "AGGRESSIVE" if rsi_1h > 65 else "NORMAL"
        guide = "🔥 AGQ 80%" if tag == "AGGRESSIVE" else "📈 AGQ 40%, SLV 40%"
    elif curr_slv < ma_1h * 0.995:
        tag = "DEFENSE" if drop_from_high <= -5.0 else "WAIT"
        guide = "🛡️ 현금 80%" if tag == "DEFENSE" else "⚠️ 현금 50%, SLV 40%"
    else:
        tag = state.get("last_tag", "WAIT")
        guide = state.get("last_guide", "⚠️ 현금 50%, SLV 40%")

    is_guide_changed = (state.get("last_guide") != guide)
    is_daily_report = (state.get("last_report_date") != today_str)

    if is_guide_changed or is_daily_report:
        title = "🔄 [Silver 비중 변동]" if is_guide_changed else "☀️ [정기 생존 보고]"
        msg = f"{title}\n💎 현재가: ${curr_slv:.2f}\n📊 상태: {tag} (RSI: {rsi_1h:.1f})\n📉 고점대비: {drop_from_high:.2f}%\n👉 행동: {guide}"
        send_msg(msg)
        
        state.update({"last_tag": tag, "last_guide": guide, "last_report_date": today_str})
        with open(STATE_FILE, "w") as f: json.dump(state, f)

except Exception as e:
    print(f"오류: {e}")
