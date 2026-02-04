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
            slv_1h = yf.download("SLV", period="7d", interval="1h", progress=False)
            slv_15m = yf.download("SLV", period="3d", interval="15m", progress=False)
            agq_15m = yf.download("AGQ", period="3d", interval="15m", progress=False)

            if slv_1h.empty or slv_15m.empty:
                raise ValueError("데이터 수집 실패")

            def get_close(df):
                if 'Close' in df.columns:
                    col = df['Close']
                    return col.iloc[:, 0] if isinstance(col, pd.DataFrame) else col
                return pd.Series()

            s_1h = get_close(slv_1h).dropna()
            s_15m = get_close(slv_15m).dropna()
            a_15m = get_close(agq_15m).dropna()

            # 지표 계산
            ma10_1h = s_1h.rolling(window=10).mean().iloc[-1]
            rsi_1h = (100 - (100 / (1 + (s_1h.diff().where(lambda x: x > 0, 0).rolling(14).mean() / 
                                        -s_1h.diff().where(lambda x: x < 0, 0).rolling(14).mean()狂)))).iloc[-1]

            return s_15m.iloc[-1], a_15m.iloc[-1], ma10_1h, rsi_1h
        
        except Exception as e:
            if i < 2: 
                time.sleep(10)
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

    # 알림 전송 (메시지에 현재가 상세 포함)
    if state.get("last_tag") is None or tag != state["last_tag"]:
        msg = f"🔄 [Silver 신호 발생]\n\n" \
              f"💎 실시간 가격 정보\n" \
              f"- SLV 현재가: ${curr_slv:.2f}\n" \
              f"- AGQ 현재가: ${curr_agq:.2f}\n" \
              f"- 1h 이평선: ${ma_1h:.2f}\n\n" \
              f"📊 상태 분석\n" \
              f"- 현재 상태: {tag}\n" \
              f"- RSI(1h): {rsi_1h:.1f}\n" \
              f"- 고점대비 낙폭: {drop_15m:.2f}%\n\n" \
              f"👉 행동 지침: {guide}"
        send_msg(msg)
        state["last_tag"] = tag

    # 야간 보고 (한국시간 23시)
    today_str = now.strftime('%Y-%m-%d')
    if now.hour == 23 and 15 <= now.minute <= 45 and state.get("last_report_date") != today_str:
        report = f"📊 [시스템 생존 보고]\n" \
                 f"📅 날짜: {today_str}\n" \
                 f"💰 SLV: ${curr_slv:.2f} / AGQ: ${curr_agq:.2f}\n" \
                 f"📈 이평선: ${ma_1h:.2f}\n" \
                 f"🏷️ 상태: {tag}\n" \
                 f"✅ 시스템 정상 작동 중"
        send_msg(report)
        state["last_report_date"] = today_str

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

except Exception as e:
    send_msg(f"❌ 데이터 분석 오류: {str(e)}")
