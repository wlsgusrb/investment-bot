import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
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

def get_realtime_data():
    try:
        # 실시간 변동을 위해 24시간 은 선물(SI=F) 데이터 사용
        silver_now = yf.download("SI=F", period="1d", interval="1m", progress=False)
        silver_1h = yf.download("SI=F", period="5d", interval="1h", progress=False)
        
        if silver_now.empty or silver_1h.empty: raise ValueError("데이터 수집 실패")

        # [수정] .iloc[-1] 뒤에 .item()이나 인덱싱을 확실히 하여 단일 값 추출
        curr_price = float(silver_now['Close'].iloc[-1])
        
        # [수정] 최근 2시간 내 최고가 추출 (에러 방지를 위해 float 변환)
        max_high = float(silver_1h['High'].iloc[-2:].max())
        
        # MA10 및 RSI 계산 (단일 시리즈로 변환하여 에러 방지)
        close_series = silver_1h['Close'].squeeze()
        ma10_1h = float(close_series.rolling(window=10).mean().iloc[-1])
        
        delta = close_series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_1h = float(100 - (100 / (1 + rs.iloc[-1])))
        
        return curr_price, ma10_1h, rsi_1h, max_high
    except Exception as e:
        raise e

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
    curr_price, ma_1h, rsi_1h, max_high = get_realtime_data()
    drop_from_high = (curr_price / max_high - 1) * 100

    # 대응 로직 (폭락 시 즉시 현금화)
    if drop_from_high <= -3.0: 
        tag, guide = "PANIC_EXIT", "🚨🚨 실시간 폭락 감지! 전량 현금화"
    elif rsi_1h >= 70:
        if rsi_1h >= 85: tag, guide = "SELL_3", "🔥 현금 80%"
        else: tag, guide = "SELL_1", "✅ 현금 30%"
    elif curr_price > ma_1h:
        tag, guide = "NORMAL", "📈 AGQ 40%, SLV 40%"
    else:
        tag, guide = "WAIT", "⚠️ 현금 50%, SLV 40%"

    is_guide_changed = (state.get("last_guide") != guide)
    is_daily_report = (state.get("last_report_date") != today_str)

    if is_guide_changed or is_daily_report:
        title = "⚠️ [실시간 시장 경보]" if is_guide_changed else "☀️ [정기 보고]"
        msg = f"{title}\n💎 실시간가: ${curr_price:.2f}\n📉 고점대비: {drop_from_high:.2f}%\n👉 대응: {guide}"
        send_msg(msg)
        
        state.update({"last_tag": tag, "last_guide": guide, "last_report_date": today_str})
        with open(STATE_FILE, "w") as f: json.dump(state, f)

except Exception as e:
    # 에러 발생 시 텔레그램으로 상세 내용 전송
    send_msg(f"❌ 봇 에러 발생: {str(e)}")
