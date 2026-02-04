import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

# ==========================================
# 1. 개인 설정 (사용자 정보 입력됨)
# ==========================================
TOKEN = "7724330685:AAFO6h59Iu0V5v-oG5Wn8_6u5p4W_EPr1V8"
CHAT_ID = "6161476106"
KST = timezone(timedelta(hours=9))

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message}
    try: 
        requests.get(url, params=params, timeout=10)
    except: 
        pass

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return None
    df = pd.DataFrame(prices, columns=['close'])
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    return float((100 - (100 / (1 + (avg_gain / avg_loss)))).iloc[-1])

def analyze():
    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now_str}] 하이브리드 분석 시작...")
    
    try:
        # 데이터 가져오기 (실시간 감시용 15분봉 & 전략용 1시간봉)
        slv_ticker = yf.Ticker("SLV")
        slv_15m = slv_ticker.history(period="1d", interval="15m")
        slv_1h = slv_ticker.history(period="1mo", interval="1h")

        if slv_15m.empty or slv_1h.empty: 
            print("데이터를 불러오지 못했습니다.")
            return

        # 1. [15분봉] 급락 체크 (생존 로직)
        prices_15m = slv_15m['Close'].tail(8).values
        if len(prices_15m) > 1:
            max_price_15m = max(prices_15m[:-1])
            curr_price_15m = prices_15m[-1]
            drop = (curr_price_15m / max_price_15m - 1) * 100
        else:
            drop = 0
        
        # 2. [1시간봉] 전략 체크 (RSI & 이평선)
        prices_1h = slv_1h['Close'].values
        curr_price = prices_1h[-1]
        rsi = calculate_rsi(prices_1h)
        ma20 = sum(prices_1h[-20:]) / 20

        # 3. 상황별 메시지 및 비중 결정
        msg = ""
        
        # A. 긴급 상황 (5% 이상 폭락)
        if drop <= -5.0:
            msg = (f"🚨 [긴급 폭락 경보]\n"
                   f"현재가: ${curr_price:.2f}\n"
                   f"단기 하락률: {drop:.2f}%\n\n"
                   f"💡 추천 비중: [현금 100%]\n"
                   f"위험 구간입니다. 일단 피신하세요!")
        
        # B. 매수 구간 (RSI 30 이하 + 이평선 아래)
        elif rsi <= 30 and curr_price < ma20 * 1.01:
            msg = (f"💰 [매수 타이밍 - 저점 포착]\n"
                   f"현재가: ${curr_price:.2f}\n"
                   f"1시간 RSI: {rsi:.2f}\n\n"
                   f"💡 추천 비중: [AGQ 80% / SLV 20%]\n"
                   f"가격이 충분히 저렴합니다. 공격적 매수 추천!")
        
        # C. 매도 구간 (RSI 70 이상 + 이평선 위)
        elif rsi >= 70 and curr_price > ma20 * 0.99:
            msg = (f"⚖️ [매도 타이밍 - 수익 실현]\n"
                   f"현재가: ${curr_price:.2f}\n"
                   f"1시간 RSI: {rsi:.2f}\n\n"
                   f"💡 추천 비중: [AGQ 10% / SLV 40% / 현금 50%]\n"
                   f"과열 구간입니다. 수익을 챙기고 현금을 확보하세요.")

        # 메시지 전송
        if msg:
            send_telegram(msg)
            print(f" > 신호 발생! 메시지 전송 완료.")
        else:
            print(f" > 현재 RSI {rsi:.2f} / 하락률 {drop:.2f}%: 특이사항 없음 (관망 중)")

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    analyze()
