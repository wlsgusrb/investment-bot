import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
import time
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

# [고정] 사용자님 기존 설정
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
            
            if slv_1h.empty or slv_15m.empty:
                raise ValueError("데이터 수집 실패")

            def get_latest_price(df):
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

# KST(한국시간) 기준 날짜
now = datetime.now()
today_str = now.strftime('%Y-%m-%d')

try:
    curr_slv, curr_agq, ma_1h, rsi_1h = get_hybrid_data()

    if curr_slv > state.get("max_high", 0):
        state["max_high"] = float(curr_slv)
    
    drop_15m = (curr_slv / state["max_high"] - 1) * 100

    # [수정] 기존 로직에 '분할 매도' 단계 추가
    if drop_15m <= -10.0:
        tag = "PANIC_EXIT"
        guide = "🚨 [긴급] 전량 현금화 (CASH 100%)"
    elif rsi_1h >= 70:
        if rsi_1h >= 85:
            tag = "SELL_STEP_3"
            guide = "🔥 [익절-3단계] CASH 80%, SLV 20% (매도 권장)"
        elif rsi_1h >= 80:
            tag = "SELL_STEP_2"
            guide = "⚖️ [익절-2단계] CASH 60%, SLV 40%"
        else:
            tag = "SELL_STEP_1"
            guide = "✅ [익절-1단계] CASH 30%, SLV 40%, AGQ 30%"
    elif curr_slv > ma_1h * 1.005:
        tag = "AGGRESSIVE" if rsi_1h > 65 else "NORMAL"
        guide = "🔥 [상승] AGQ 80%, SLV 20%" if tag == "AGGRESSIVE" else "📈 [안정] AGQ 40%, SLV 40%, CASH 20%"
    elif curr_slv < ma_1h * 0.995:
        tag = "DEFENSE" if drop_15m <= -5.0 else "WAIT"
        guide = "🛡️ [방어] CASH 80%, SLV 20%" if tag == "DEFENSE" else "⚠️ [관망] CASH 50%, SLV 40%, AGQ 10%"
    else:
        tag = state.get("last_tag", "WAIT")
        guide = "횡보 중 (이전 비중 유지)"

    # [수정] 신호 변동 알림 + 24시간 정기 보고 통합
    is_new_signal = (state.get("last_tag") is None or tag != state["last_tag"])
    is_time_for_report = (state.get("last_report_date") != today_str)

    if is_new_signal or is_time_for_report:
        msg_header = "🔄 [Silver 신호 변동]" if is_new_signal else "☀️ [24시간 정기 보고]"
        msg = f"{msg_header}\n\n" \
              f"💎 실시간 가격\n" \
              f"- SLV: ${curr_slv:.2f}\n" \
              f"- AGQ: ${curr_agq:.2f}\n" \
              f"- 기준이평선: ${ma_1h:.2f}\n\n" \
              f"📊 상태: {tag} (RSI: {rsi_1h:.1f})\n" \
              f"📉 고점대비: {drop_15m:.2f}%\n" \
              f"👉 행동: {guide}"
        
        send_msg(msg)
        state["last_tag"] = tag
        state["last_report_date"] = today_str # 전송 후 날짜 갱신

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

except Exception as e:
    print(f"오류 발생: {e}")
