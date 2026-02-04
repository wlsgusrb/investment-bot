import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

# 1. 개인 설정
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
KST = timezone(timedelta(hours=9))

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message}
    try: requests.get(url, params=params, timeout=10)
    except: pass

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
    print(f"[{datetime.now(KST)}] 하이브리드 분석 시작...")
    try:
        # 데이터 가져오기 (15분봉 & 1시간봉)
        slv_15m = yf.Ticker("SLV").history(period="1d", interval="15m")
        slv_1h = yf.Ticker("SLV").history(period="1mo", interval="1h")

        if slv_15m.empty or slv_1h.empty: return

        # 1. [15분봉] 급락 체크 (생존 로직)
        prices_15m = slv_15m['Close'].tail(8).values
        drop = (prices_15m[-1] / max(prices_15m[:-1]) - 1) * 100
        
        # 2. [1시간봉] 전략 체크 (RSI & 이평선)
        prices_1h = slv_1h['Close'].values
        curr_price = prices_1h[-1]
        rsi = calculate_rsi(prices_1h)
        ma20 = sum(prices_1h[-20:]) / 20

        # 3. 상황별 추천 비중 결정 로직
        msg = ""
        if drop <= -5.0:
            msg = f"🚨 [긴급 폭락 경보]\n현재가: ${curr_price:.2f}\n단기 하락률: {drop:.2f}%\n\n💡 추천 비중: [현금 100%]\n위험 구간입니다. 일단 피하세요!"
        elif rsi <= 30 and curr_price < ma20 * 1.01:
            msg = f"💰 [매수 타이밍]\n현재가: ${curr_price:.2f}\nRSI: {rsi:.2f}\n\n💡 추천 비중: [AGQ 80% / SLV 20%]\n저점입니다. 공격적 매수 구간!"
        elif rsi >= 70 and curr_price > ma20 * 0.99:
            msg = f"⚖️ [매도 타이밍]\n현재가: ${curr_price:.2f}\nRSI: {rsi:.2f}\n\n💡 추천 비중: [AGQ 10% / SLV 40% / 현금 50%]\n고점입니다. 수익을 실현하세요."
        # 특별한 신호가 없으면 알림을 보내지 않음 (거래 횟수 조절)
        
        if msg:
            send_telegram(msg)
            print(" > 신호 발생! 텔레그램 전송 완료.")
        else:
            print(f" > 현재 RSI {rsi:.2f}: 특이사항 없음 (관망)")

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    analyze()
