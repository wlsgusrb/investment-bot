import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# [1. 사용자 설정]
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"
STATE_FILE = "portfolio_state.json"

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e: print(f"텔레그램 에러: {e}")

def get_strategy_data():
    ticker = "SLV"
    df = yf.download(ticker, period="40d", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    df['MA20'] = df['Close'].rolling(window=20).mean()
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    curr_price = float(df['Close'].iloc[-1])
    prev_high = float(df['High'].iloc[-2])
    ma20 = float(df['MA20'].iloc[-1])
    rsi = float(df['RSI'].iloc[-1])
    drop_rate = (curr_price / prev_high - 1) * 100
    
    return curr_price, ma20, rsi, drop_rate

# 상태 관리
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f: state = json.load(f)
    except: state = {"last_tag": "", "last_report_date": ""}
else:
    state = {"last_tag": "", "last_report_date": ""}

try:
    curr_price, ma20, rsi, drop_rate = get_strategy_data()
    
    now_utc = datetime.utcnow()
    now_kor = now_utc + timedelta(hours=9)
    today_str = now_kor.strftime('%Y-%m-%d')
    current_hour = now_kor.hour

    # --- [수정 구간] 전략 로직 (백테스트 성공 수치 반영) ---
    if drop_rate <= -10.0:
        tag, alloc = "PANIC_EXIT", "현금 100% (전량매도)"
    elif rsi >= 83:  # 기존 80 -> 83 상향
        tag, alloc = "SELL_83", "현금 70% : AGQ 15% : SLV 15%"
    elif rsi >= 78:  # 기존 75 -> 78 상향
        tag, alloc = "SELL_78", "현금 40% : AGQ 30% : SLV 30%"
    elif curr_price > ma20 * 1.03:  # 기존 1.02 -> 1.03 상향 (횡보장 필터 강화)
        tag, alloc = "NORMAL", "현금 10% : AGQ 45% : SLV 45%"
    elif curr_price < ma20 * 0.97:  # 기존 0.98 -> 0.97 하향 (횡보장 필터 강화)
        tag, alloc = "WAIT", "현금 40% : AGQ 20% : SLV 40%"
    else:
        # 횡보 구간 (±3% 이내) 시 이전 상태 유지
        tag = state.get("last_tag", "WAIT")
        alloc_map = {
            "PANIC_EXIT": "현금 100%", 
            "SELL_83": "현금 70% : AGQ 15% : SLV 15%",
            "SELL_78": "현금 40% : AGQ 30% : SLV 30%", 
            "NORMAL": "현금 10% : AGQ 45% : SLV 45%",
            "WAIT": "현금 40% : AGQ 20% : SLV 40%"
        }
        alloc = alloc_map.get(tag, "비중 유지")

    # [조건 1] 전략 태그가 바뀌었을 때 (실시간 알림)
    is_changed = (state.get("last_tag") != tag)
    
    # [조건 2] 아침 9시 정기 보고
    is_report_time = (current_hour == 9 and state.get("last_report_date") != today_str)

    if is_changed or is_report_time:
        if is_changed:
            title = "🔄 [긴급! 전략 변동 알림]"
        else:
            title = "☀️ [아침 정기 보고 - 시스템 정상]"

        msg = (f"{title}\n\n"
               f"📅 날짜: {today_str}\n"
               f"📊 현재 상태: {tag}\n"
               f"💡 권장 비중: {alloc}\n\n"
               f"------------------------\n"
               f"💰 현재가: ${curr_price:.2f}\n"
               f"📈 RSI: {rsi:.1f}\n"
               f"📉 고점대비: {drop_rate:.1f}%\n"
               f"------------------------\n"
               f"✅ 봇이 시장을 24시간 감시 중입니다.")
        
        send_msg(msg)
        
        state.update({"last_tag": tag, "last_report_date": today_str})
        with open(STATE_FILE, "w") as f: json.dump(state, f)

except Exception as e:
    print(f"오류 발생: {e}")
