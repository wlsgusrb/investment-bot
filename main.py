import yfinance as yf
import pandas as pd
import time
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. 투자 설정 (튜닝된 수치 적용)
# ==========================================
TICKER = "SLV"
CASH_TICKER = "CASH"  # 현금 보유 시 표시용

# 비중 설정 (C: Cash, A: AGQ(2x), S: SLV(1x))
ALLOCATION = {
    "PANIC_EXIT": {"Cash": 1.0, "AGQ": 0.0, "SLV": 0.0}, # 현금 100%
    "SELL_83":    {"Cash": 0.7, "AGQ": 0.15, "SLV": 0.15}, # 수익 확정
    "SELL_78":    {"Cash": 0.4, "AGQ": 0.3, "SLV": 0.3},  # 분할 익절
    "NORMAL":     {"Cash": 0.1, "AGQ": 0.45, "SLV": 0.45}, # 공격형 투자
    "WAIT":       {"Cash": 0.4, "AGQ": 0.2, "SLV": 0.4}   # 방어형 투자
}

# 상태 저장 변수 (횡보장 판단용)
last_status = "WAIT" 

def get_market_data():
    """실시간 시장 데이터 수집 및 지표 계산"""
    try:
        df = yf.download(TICKER, period="60d", interval="1d", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 지표 계산
        df['MA20'] = df['Close'].rolling(window=20).mean()
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        return df.iloc[-1], df.iloc[-2] # 오늘 데이터, 어제 데이터
    except Exception as e:
        print(f"데이터 수집 중 오류: {e}")
        return None, None

def decide_strategy(curr, prev_day, current_status):
    """튜닝된 횡보장 필터 로직 적용"""
    price = float(curr['Close'])
    ma20 = float(curr['MA20'])
    rsi = float(curr['RSI'])
    prev_high = float(prev_day['High'])
    
    # 1. 폭락 감지 (패닉 셀)
    drop_rate = (price / prev_high - 1) * 100
    if drop_rate <= -10.0:
        return "PANIC_EXIT"
    
    # 2. 과열 감지 (익절)
    if rsi >= 83: return "SELL_83"
    if rsi >= 78: return "SELL_78"
    
    # 3. 추세 판단 (±3% 횡보장 필터 핵심)
    dist = price / ma20
    
    if dist > 1.03:    # 3% 이상 상방 돌파 시만 상승장으로 인정
        return "NORMAL"
    elif dist < 0.97:  # 3% 이상 하방 돌파 시만 하락장으로 인정
        return "WAIT"
    else:
        # ±3% 이내 횡보 시에는 '이전 상태'를 그대로 유지 (잦은 매매 방지)
        return current_status

def execute_trade(status):
    """최종 결정된 비중에 따라 매매 지시 (출력용)"""
    alloc = ALLOCATION[status]
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 매매 보고서")
    print(f"설정된 상태: {status}")
    print(f"최종 비중 -> 현금: {alloc['Cash']*100:.0f}% | AGQ(2x): {alloc['AGQ']*100:.0f}% | SLV(1x): {alloc['SLV']*100:.0f}%")
    print("--------------------------------------------------")

# ==========================================
# 2. 실전 루프 가동
# ==========================================
print("🚀 튜닝된 은 매매 봇(횡보장 강화 버전) 가동을 시작합니다.")

while True:
    now = datetime.now()
    # 장 중에만 작동하도록 설정 가능 (여기서는 테스트를 위해 즉시 실행 루프)
    
    curr_data, prev_data = get_market_data()
    
    if curr_data is not None:
        # 새로운 상태 결정
        new_status = decide_strategy(curr_data, prev_data, last_status)
        
        # 상태 변화가 있을 때만 매매 실행 (또는 주기적 보고)
        if new_status != last_status:
            print(f"📢 상태 변경 감지: {last_status} -> {new_status}")
            execute_trade(new_status)
            last_status = new_status
        else:
            print(f"😴 현재 {last_status} 상태 유지 중... (가격: {curr_data['Close']:.2f}, RSI: {curr_data['RSI']:.1f})")
            
    # 1시간마다 체크 (실전 매매 주기에 맞춰 조절)
    time.sleep(3600)
