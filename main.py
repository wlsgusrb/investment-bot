import yfinance as yf
import pandas as pd
import requests
import json
import os
import warnings
from datetime import datetime

# 1. 경고 및 설정
warnings.filterwarnings('ignore')

# 🔔 사용자 정보 (사용자님이 요청하신 값 그대로 유지)
TELEGRAM_TOKEN = "8554003778:AAFfIJzzeaPfymzoVbzrhGaOXSB8tQYGVNw"
TELEGRAM_CHAT_ID = "-1003476098424"
STATE_FILE = "portfolio_state.json"  # 2단계에서 말씀드린 대로 파일명 통일

def send_msg(msg):
    """텔레그램 메시지 전송 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        res = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        if res.status_code == 200:
            print("✅ 텔레그램 메시지 전송 성공!")
        else:
            print(f"❌ 전송 실패 (상태 코드: {res.status_code})")
    except Exception as e:
        print(f"❌ 메시지 전송 에러: {e}")

def get_hybrid_data():
    """데이터 수집 및 지표 계산"""
    # 프리/애프터장 포함 데이터 수집
    df_1h = yf.download("SLV", period="5d", interval="1h", progress=False, include_post=True)
    df_15m = yf.download("SLV", period="2d", interval="15m", progress=False, include_post=True)
    df_agq_15m = yf.download("AGQ", period="2d", interval="15m", progress=False, include_post=True)
    
    def clean(df):
        if 'Close' in df.columns:
            res = df['Close']
            if isinstance(res, pd.DataFrame): res = res.iloc[:, 0]
            return res.dropna()
        return pd.Series()

    slv_1h = clean(df_1h)
    slv_15m = clean(df_15m)
    agq_15m = clean(df_agq_15m)

    # 지표 계산
    ma10_1h = slv_1h.rolling(window=10).mean().iloc[-1]
    delta = slv_1h.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi_1h = (100 - (100 / (1 + (gain / loss)))).iloc[-1]
    
    return slv_15m.iloc[-1], agq_15m.iloc[-1], ma10_1h, rsi_1h

# --- 메인 실행 로직 ---

# 1. 상태 로드
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except:
        state = {"last_tag": None, "max_high": 0, "last_report_date": ""}
else:
    state = {"last_tag": None, "max_high": 0, "last_report_date": ""}

# 2. 데이터 수집
now = datetime.now()
try:
    curr_slv, curr_agq, ma_1h, rsi_1h = get_hybrid_data()
except Exception as e:
    send_msg(f"❌ 데이터 수집 실패: {e}")
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
    guide = "횡보 중 (이전 비중 유지)"

# 5. 알림 전송 (신호가 처음이거나 변했을 때만)
# 처음 실행 시 무조건 한 번 알림을 보내도록 강제
if state.get("last_tag") is None or tag != state.get("last_tag"):
    msg = f"🔄 [Silver 포트폴리오 신호 발생]\n\n" \
          f"⏰ 시간: {now.strftime('%H:%M')}\n" \
          f"🏷️ 상태: {tag}\n" \
          f"💰 SLV: ${curr_slv:.2f} / AGQ: ${curr_agq:.2f}\n" \
          f"📉 낙폭: {drop_15m:.2f}% / RSI: {rsi_1h:.1f}\n\n" \
          f"👉 행동: {guide}"
    send_msg(msg)
    state["last_tag"] = tag

# 6. 시스템 생존 보고 (밤 11시 30분대 실행 시)
today_str = now.strftime('%Y-%m-%d')
if now.hour == 23 and 15 <= now.minute <= 45 and state.get("last_report_date") != today_str:
    report = f"📊 [시스템 정상 작동 보고]\n\n" \
             f"📅 날짜: {today_str}\n" \
             f"💎 현재가 SLV: ${curr_slv:.2f} / AGQ: ${curr_agq:.2f}\n" \
             f"현재 '{tag}' 상태로 운영 중입니다."
    send_msg(report)
    state["last_report_date"] = today_str

# 7. 상태 저장 (이게 되어야 중복 알림이 안 옴)
with open(STATE_FILE, "w") as f:
    json.dump(state, f)
