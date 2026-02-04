import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
import time
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

def get_hybrid_data():
    for i in range(3):
        try:
            # period를 넉넉히 잡고 최신 순으로 정렬하여 정확도 향상
            slv_1h = yf.download("SLV", period="5d", interval="1h", progress=False)
            slv_15m = yf.download("SLV", period="2d", interval="15m", progress=False)
            agq_15m = yf.download("AGQ", period="2d", interval="15m", progress=False)

            if slv_1h.empty or slv_15m.empty:
                raise ValueError("데이터 수집 실패")

            def get_latest_price(df):
                # 데이터프레임의 가장 마지막 행(최신)을 가져오되 결측치 제외
                close_data = df['Close']
                if isinstance(close_data, pd.DataFrame):
                    close_data = close_data.iloc[:, 0]
                return close_data.dropna().iloc[-1]

            def get_ma_latest(df, window=10):
                close_data = df['Close']
                if isinstance(close_data, pd.DataFrame):
                    close_data = close_data.iloc[:, 0]
                return close_data.rolling(window=window).mean().dropna().iloc[-1]

            curr_slv = get_latest_price(slv_15m)
            curr_agq = get_latest_price(agq_15m)
            ma10_1h = get_ma_latest(slv_1h)
            
            # RSI 계산
            s_1h = slv_1h['Close']
            if isinstance(s_1h, pd.DataFrame): s_1h = s_1h.iloc[:, 0]
            delta = s_1h.diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rsi_1h = (100 - (100 / (1 + (gain / loss)))).dropna().iloc[-1]

            return curr_slv, curr_agq, ma10_1h, rsi_1h
        
        except Exception as e:
            if i < 2: 
                time.sleep(5)
                continue
            else:
                raise e

# --- 메인 실행 ---
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except:
        state = {"last_tag": None, "max_high": 0, "last_report_date": ""}
else:
    state = {"last_tag": None, "max_high": 0, "last_report_date": ""}

now = datetime.now()
try:
    curr_slv, curr_agq, ma_1h, rsi_1h = get_hybrid_data()
    
    if curr_slv > state.get("max_high", 0):
        state["max_high"] = float(curr_slv)
    drop_15m = (curr_slv / state["max_high"] - 1) * 100

    # 로직 판단
    if drop_15m <= -10.0:
        tag = "PANIC_EXIT"
        guide = "🚨 [긴급] 전량 현금화 (CASH 100%)"
    elif curr_slv > ma_1h * 1.005:
        tag = "AGGRESSIVE" if rsi_1h > 65 else "NORMAL"
        guide = "🔥 [상승] AGQ 80%, SLV 20%" if tag == "AGGRESSIVE" else "📈 [안정] AGQ 40%, SLV 40%, CASH 20%"
    elif curr_slv < ma_1h * 0.995:
        tag = "DEFENSE" if drop_15m <= -5.0 else "WAIT"
        guide = "🛡️ [방어] CASH 80%, SLV 20%" if tag == "DEFENSE" else "⚠️ [관망] CASH 50%, SLV 40%, AGQ 10%"
    else:
        tag = state.get("last_tag", "WAIT")
        guide = "횡보 중 (이전 비중 유지)"

    # 알림 전송 (항상 15분마다 최신가를 확인하고 싶다면 아래 조건을 수정할 수 있습니다)
    if state.get("last_tag") is None or tag != state["last_tag"]:
        msg = f"🔄 [Silver 신호 변동]\n\n" \
              f"💎 실시간 가격 (Yahoo 지연)\n" \
              f"- SLV: ${curr_slv:.2f}\n" \
              f"- AGQ: ${curr_agq:.2f}\n" \
              f"- 기준이평선: ${ma_1h:.2f}\n\n" \
              f"📊 상태: {tag} (RSI: {rsi_1h:.1f})\n" \
              f"📉 고점대비: {drop_15m:.2f}%\n" \
              f"👉 행동: {guide}"
        send_msg(msg)
        state["last_tag"] = tag

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

except Exception as e:
    # 텔레그램으로 에러를 보내지 않고 로그만 남김 (너무 잦은 에러 알림 방지)
    print(f"오류 발생: {e}")
