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
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 하이브리드 전략 분석 중...")
    
    try:
        slv = yf.Ticker("SLV")
        slv_15m = slv.history(period="1d", interval="15m")
        slv_1h = slv.history(period="1mo", interval="1h")

        if slv_15m.empty or slv_1h.empty: return

        # 1. 급락 체크 (-5%)
        prices_15m = slv_15m['Close'].tail(8).values
        drop = (prices_15m[-1] / max(prices_15m[:-1]) - 1) * 100 if len(prices_15m) > 1 else 0
        
        # 2. 전략 지표 (RSI & MA20)
        prices_1h = slv_1h['Close'].values
        curr_price = prices_1h[-1]
        rsi = calculate_rsi(prices_1h)
        ma20 = sum(prices_1h[-20:]) / 20

        msg = ""

        # [상황 A] 비상 상황 (폭락)
        if drop <= -5.0:
            msg = f"🚨 [긴급 폭락 경보]\n현재가: ${curr_price:.2f}\n하락률: {drop:.2f}%\n💡 추천: [전량 현금화]"

        # [상황 B] 매수 타이밍 (RSI 30 이하)
        elif rsi <= 30 and curr_price < ma20 * 1.01:
            msg = f"💰 [매수 타이밍]\nRSI: {rsi:.2f}\n💡 추천: [AGQ 80% / SLV 20%]\n저점 포착, 공격적 진입!"

        # [상황 C] 분할 매도 타이밍 (단계별 수익 실현)
        elif rsi >= 70 and curr_price > ma20 * 0.98:
            if rsi >= 85:
                msg = f"🔥 [분할 매도 - 3단계]\nRSI: {rsi:.2f}\n💡 추천: [현금 80% / SLV 20%]\n극대과열! 수익을 거의 다 챙기세요."
            elif rsi >= 80:
                msg = f"⚖️ [분할 매도 - 2단계]\nRSI: {rsi:.2f}\n💡 추천: [현금 60% / SLV 40%]\n고점 부근입니다. 비중을 더 줄이세요."
            else:
                msg = f"✅ [분할 매도 - 1단계]\nRSI: {rsi:.2f}\n💡 추천: [현금 30% / SLV 40% / AGQ 30%]\n수익 실현 시작! 나머지는 더 가져가 봅니다."

        # [상황 D] 24시간 주기 정기 보고
        report_file = "last_report.txt"
        should_report = False
        
        if not os.path.exists(report_file):
            should_report = True # 처음 실행 시 즉시 보고
        else:
            with open(report_file, "r") as f:
                last_time = datetime.fromisoformat(f.read())
            if now - last_time >= timedelta(hours=24):
                should_report = True

        if should_report and not msg: # 매매 신호가 없을 때만 정기 보고
            msg = (f"☀️ [24시간 정기 생존 보고]\n"
                   f"현재가: ${curr_price:.2f}\n"
                   f"RSI: {rsi:.2f}\n"
                   f"상태: 정상 감시 중 (신호 없음)")
            with open(report_file, "w") as f:
                f.write(now.isoformat())
        elif msg: # 매매 신호가 발생했다면 보고 시간 갱신 (보고를 대신함)
            with open(report_file, "w") as f:
                f.write(now.isoformat())

        if msg:
            send_telegram(msg)

    except Exception as e:
        print(f"에러: {e}")

if __name__ == "__main__":
    analyze()
if __name__ == "__main__":
    send_telegram("테스트 메시지: 봇이 살아있습니다!") # 이 줄을 추가
    analyze()
