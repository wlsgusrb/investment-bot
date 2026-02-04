import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
import time
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# [유지] 사용자님 설정값 (절대 수정 금지)
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
            # [수정] 고점 계산을 위해 최근 5일치 데이터를 가져옴
            slv_1h = yf.download("SLV", period="5d", interval="1h", progress=False)
            slv_15m = yf.download("SLV", period="2d", interval="15m", progress=False)
            agq_15m = yf.download("AGQ", period="2d", interval="15m", progress=False)
            
            if slv_1h.empty or slv_15m.empty:
                raise ValueError("데이터 수집 실패")

            def get_latest_price(df):
                close_data = df['Close']
                if isinstance(close_data, pd.DataFrame): close_data = close_data.iloc[:, 0]
                return close_data.dropna().iloc[-1]

            def get_ma_latest(df, window=10):
                close_data = df['Close']
                if isinstance(close_data, pd.DataFrame): close_data = close_data.iloc[:, 0]
                return close_data.rolling(window=window).mean().dropna().iloc[-1]

            curr_slv = get_latest_price(slv_15m)
            curr_agq = get_latest_price(agq_15m)
            ma10_1h = get_ma_latest(slv_1h)

            # [수정] 옵션 A: 최근 5일 데이터 중 최고가를 실시간 고점으로 사용
            max_high_5d = float(slv_1h['High'].max())

            s_1h = slv_1h['Close']
            if isinstance(s_1h, pd.DataFrame): s_1h = s_1h.iloc[:, 0]
            delta = s_1h.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_1h = (100 - (100 / (1 + (gain / loss)))).dropna().iloc[-1]
            
            return curr_slv, curr_agq, ma10_1h, rsi_1h, max_high_5d

        except Exception as e:
            if i < 2: time.sleep(5); continue
            else: raise e

# --- 메인 실행 ---
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except:
        state = {"last_tag": None}
else:
    state = {"last_tag": None}

try:
    curr_slv, curr_agq, ma_1h, rsi_1h, max_high = get_hybrid_data()
    drop_from_high = (curr_slv / max_high - 1) * 100

    # 로직 판단
    if drop_from_high <= -10.0:
        tag = "PANIC_EXIT"
        guide = "🚨 [긴급] 전량 현금화 (CASH 100%)"
    elif rsi_1h >= 70:
        if rsi_1h >= 85: tag = "SELL_3"; guide = "🔥 [익절-3] 현금 80%"
        elif rsi_1h >= 80: tag = "SELL_2"; guide = "⚖️ [익절-2] 현금 60%"
        else: tag = "SELL_1"; guide = "✅ [익절-1] 현금 30%"
    elif curr_slv > ma_1h * 1.005:
        tag = "AGGRESSIVE" if rsi_1h > 65 else "NORMAL"
        guide = "🔥 AGQ 80%" if tag == "AGGRESSIVE" else "📈 AGQ 40%, SLV 40%"
    elif curr_slv < ma_1h * 0.995:
        tag = "DEFENSE" if drop_from_high <= -5.0 else "WAIT"
        guide = "🛡️ 현금 80%" if tag == "DEFENSE" else "⚠️ 현금 50%, SLV 40%"
    else:
        tag = state.get("last_tag", "WAIT")
        guide = "횡보 중 (비중 유지)"

    # [수정] 비중(tag)이 바뀔 때만 알림 전송 (정기 보고 삭제)
    if state.get("last_tag") != tag:
        msg = f"🔄 [Silver 신호 변동]\n\n" \
              f"💎 현재가: ${curr_slv:.2f}\n" \
              f"📊 상태: {tag} (RSI: {rsi_1h:.1f})\n" \
              f"📉 5일고점대비: {drop_from_high:.2f}%\n" \
              f"👉 행동: {guide}"
        
        send_msg(msg)
        state["last_tag"] = tag

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

except Exception as e:
    print(f"오류 발생: {e}")
