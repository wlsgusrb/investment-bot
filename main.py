import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
from datetime import datetime

# 경고 무시 및 설정
warnings.filterwarnings('ignore')

# 🔔 사용자 설정 (기존 정보 유지)
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"
STATE_FILE = "hybrid_trading_state.json"

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"메시지 전송 에러: {e}")

def get_hybrid_data():
    # 데이터 추출 (1시간봉 & 15분봉) - 프리/애프터장 포함을 위해 include_post=True
    df_1h = yf.download("SLV", period="5d", interval="1h", progress=False, include_post=True)
    df_15m = yf.download("SLV", period="2d", interval="15m", progress=False, include_post=True)
    df_agq_15m = yf.download("AGQ", period="2d", interval="15m", progress=False, include_post=True)
    
    # 데이터 클리닝 (멀티인덱스 대응)
    def clean(df):
        if 'Close' in df.columns:
            res = df['Close']
            if isinstance(res, pd.DataFrame): res = res.iloc[:, 0]
            return res.dropna()
        return pd.Series()

    slv_1h = clean(df_1h)
    slv_15m = clean(df_15m)
    agq_15m = clean(df_agq_15m)

    # 1시간봉 지표 계산
    ma10_1h = slv_1h.rolling(window=10).mean().iloc[-1]
    delta = slv_1h.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_1h = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
    
    # 현재가 (SLV, AGQ)
    curr_slv = slv_15m.iloc[-1]
    curr_agq = agq_15m.iloc[-1]
    
    return curr_slv, curr_agq, ma10_1h, rsi_1h

# 1. 상태 로드
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except:
        state = {"last_tag": None, "max_high": 0, "last_report_date": ""}
else:
    state = {"last_tag": None, "max_high": 0, "last_report_date": ""}

# 2. 데이터 가져오기
now = datetime.now()
try:
    curr_slv, curr_agq, ma_1h, rsi_1h = get_hybrid_data()
except Exception as e:
    print(f"데이터 가져오기 실패: {e}")
    exit()

# 3. 전고점 관리 (15분봉 기준)
if curr_slv > state.get("max_high", 0):
    state["max_high"] = float(curr_slv)
drop_15m = (curr_slv / state["max_high"] - 1) * 100

# 4. 하이브리드 판단 로직
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
    guide = "횡보 중 (기존 비중 유지)"

# 5. 알림 전송 (신호 변화 시)
if tag != state.get("last_tag"):
    msg = f"🔄 [포지션 변경 알림]\n\n" \
          f"🏷️ 상태: {tag}\n" \
          f"💰 SLV: ${curr_slv:.2f} / AGQ: ${curr_agq:.2f}\n" \
          f"📉 낙폭: {drop_15m:.2f}% / RSI: {rsi_1h:.1f}\n\n" \
          f"👉 행동: {guide}"
    send_msg(msg)
    state["last_tag"] = tag

# 6. 매일 미국 본장 시작 알림 (정상 작동 확인용)
# 서머타임 고려 없이 23:30분 기준 (또는 22:30분으로 수정 가능)
today_str = now.strftime('%Y-%m-%d')
if now.hour == 23 and now.minute <= 15 and state.get("last_report_date") != today_str:
    report = f"📊 [시스템 정상 작동 보고]\n\n" \
             f"📅 날짜: {now.strftime('%Y-%m-%d %H:%M')}\n" \
             f"💎 현재가 정보\n" \
             f"- SLV: ${curr_slv:.2f}\n" \
             f"- AGQ: ${curr_agq:.2f}\n\n" \
             f"현재 '{tag}' 상태로 운영 중입니다."
    send_msg(report)
    state["last_report_date"] = today_str

# 7. 상태 저장
with open(STATE_FILE, "w") as f:
    json.dump(state, f)
