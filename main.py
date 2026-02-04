import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

# 1. 개인 설정
TOKEN = "7724330685:AAFO6h59Iu0V5v-oG5Wn8_6u5p4W_EPr1V8"
CHAT_ID = "6161476106"
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
    now = datetime.now(KST)
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{now_str}] 분석 시작...")
    
    try:
        slv_ticker = yf.Ticker("SLV")
        slv_15m = slv_ticker.history(period="1d", interval="15m")
        slv_1h = slv_ticker.history(period="1mo", interval="1h")

        if slv_15m.empty or slv_1h.empty: return

        # 데이터 가공
        prices_15m = slv_15m['Close'].tail(8).values
        drop = (prices_15m[-1] / max(prices_15m[:-1]) - 1) * 100 if len(prices_15m) > 1 else 0
        
        prices_1h = slv_1h['Close'].values
        curr_price = prices_1h[-1]
        rsi = calculate_rsi(prices_1h)
        ma20 = sum(prices_1h[-20:]) / 20

        msg = ""
        # [조건 1] 급락 경보
        if drop <= -5.0:
            msg = f"🚨 [긴급 폭락 경보]\n현재가: ${curr_price:.2f}\n하락률: {drop:.2f}%\n💡 추천: [현금 100%]"
        
        # [조건 2] 매수/매도 타이밍
        elif rsi <= 30 and curr_price < ma20 * 1.01:
            msg = f"💰 [매수 타이밍]\n현재가: ${curr_price:.2f}\nRSI: {rsi:.2f}\n💡 추천: [AGQ 80% / SLV 20%]"
        elif rsi >= 70 and curr_price > ma20 * 0.99:
            msg = f"⚖️ [매도 타이밍]\n현재가: ${curr_price:.2f}\nRSI: {rsi:.2f}\n💡 추천: [AGQ 10% / SLV 40% / 현금 50%]"

        # [조건 3] 매일 아침 9시 정기 보고 (9:00 ~ 9:15 사이 실행 시)
        # 매수/매도 신호가 없을 때만 정기 보고를 보냅니다. (신호가 있으면 신호가 우선)
        if not msg and now.hour == 9 and now.minute < 15:
            msg = (f"☀️ [정기 생존 보고]\n"
                   f"시간: {now_str}\n"
                   f"현재가: ${curr_price:.2f}\n"
                   f"RSI: {rsi:.2f}\n"
                   f"상태: 정상 작동 중 (관망)")

        if msg:
            send_telegram(msg)
            print(f" > 메시지 전송 완료: {msg}")

    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    analyze()
