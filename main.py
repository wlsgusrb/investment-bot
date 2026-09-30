import os
import json
import time
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

# ============================================================
# [1. 사용자 설정]
# ============================================================

# 환경변수에서 가져옵니다.
# Windows:
#   set TELEGRAM_TOKEN=발급받은토큰
#   set TELEGRAM_CHAT_ID=-1003476098424
#
# Linux/macOS:
#   export TELEGRAM_TOKEN="발급받은토큰"
#   export TELEGRAM_CHAT_ID="-1003476098424"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "portfolio_state.json"

TICKER = "SLV"
TIMEZONE = "Asia/Seoul"

# 데이터 설정
DOWNLOAD_PERIOD = "40d"
DOWNLOAD_INTERVAL = "1d"

# ============================================================
# [2. 기본 검증]
# ============================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN 환경변수가 설정되지 않았습니다.")

if not TELEGRAM_CHAT_ID:
    raise RuntimeError("TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다.")


# ============================================================
# [3. Telegram 메시지 전송]
# ============================================================

def send_msg(msg, max_retries=3):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                data=payload,
                timeout=10
            )

            response.raise_for_status()

            result = response.json()

            if result.get("ok"):
                print("Telegram 메시지 전송 성공")
                return True

            print(f"Telegram API 오류: {result}")

        except requests.RequestException as e:
            print(
                f"Telegram 전송 실패 "
                f"({attempt}/{max_retries}): {e}"
            )

        except Exception as e:
            print(f"Telegram 처리 오류: {e}")

        if attempt < max_retries:
            time.sleep(2)

    return False


# ============================================================
# [4. 상태 파일]
# ============================================================

DEFAULT_STATE = {
    "last_tag": "",
    "last_report_date": ""
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return DEFAULT_STATE.copy()

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            state = json.load(f)

        if not isinstance(state, dict):
            return DEFAULT_STATE.copy()

        return {
            "last_tag": state.get("last_tag", ""),
            "last_report_date": state.get(
                "last_report_date",
                ""
            )
        }

    except Exception as e:
        print(f"상태 파일 읽기 오류: {e}")
        return DEFAULT_STATE.copy()


def save_state(state):
    temp_file = STATE_FILE + ".tmp"

    try:
        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                state,
                f,
                ensure_ascii=False,
                indent=2
            )

        # 임시 파일을 정상 파일로 교체
        os.replace(temp_file, STATE_FILE)

    except Exception as e:
        print(f"상태 파일 저장 오류: {e}")

        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass


# ============================================================
# [5. 시장 데이터 가져오기]
# ============================================================

def get_strategy_data():

    print(f"{TICKER} 데이터 다운로드 중...")

    df = yf.download(
        TICKER,
        period=DOWNLOAD_PERIOD,
        interval=DOWNLOAD_INTERVAL,
        progress=False,
        auto_adjust=False,
        threads=False
    )

    if df is None or df.empty:
        raise ValueError("Yahoo Finance 데이터가 비어 있습니다.")

    # MultiIndex 컬럼 처리
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required_columns = ["Close", "High"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(
                f"필수 데이터 '{col}'가 없습니다."
            )

    # 숫자형 변환
    df["Close"] = pd.to_numeric(
        df["Close"],
        errors="coerce"
    )

    df["High"] = pd.to_numeric(
        df["High"],
        errors="coerce"
    )

    df = df.dropna(subset=["Close", "High"]).copy()

    if len(df) < 20:
        raise ValueError(
            f"분석에 필요한 데이터가 부족합니다. "
            f"현재 {len(df)}개"
        )

    # --------------------------------------------------------
    # MA20
    # --------------------------------------------------------

    df["MA20"] = (
        df["Close"]
        .rolling(window=20)
        .mean()
    )

    # --------------------------------------------------------
    # RSI 14
    # 기존 코드와 동일한 SMA 방식
    # --------------------------------------------------------

    delta = df["Close"].diff()

    gain = (
        delta.where(delta > 0, 0)
        .rolling(window=14)
        .mean()
    )

    loss = (
        (-delta.where(delta < 0, 0))
        .rolling(window=14)
        .mean()
    )

    # 0으로 나누는 문제 방지
    rs = gain / loss.replace(0, float("nan"))

    df["RSI"] = 100 - (
        100 / (1 + rs)
    )

    # 상승만 지속되는 경우 RSI = 100
    df.loc[
        (loss == 0) & (gain > 0),
        "RSI"
    ] = 100

    # 하락/상승 모두 없는 경우 RSI = 50
    df.loc[
        (loss == 0) & (gain == 0),
        "RSI"
    ] = 50

    # 필요한 지표가 계산됐는지 확인
    latest = df.iloc[-1]

    if pd.isna(latest["MA20"]):
        raise ValueError("MA20 계산 결과가 NaN입니다.")

    if pd.isna(latest["RSI"]):
        raise ValueError("RSI 계산 결과가 NaN입니다.")

    # --------------------------------------------------------
    # 현재값
    # --------------------------------------------------------

    curr_price = float(latest["Close"])
    ma20 = float(latest["MA20"])
    rsi = float(latest["RSI"])

    # 직전 거래일 고가
    prev_high = float(df["High"].iloc[-2])

    if prev_high <= 0:
        raise ValueError("직전 고가가 비정상적입니다.")

    drop_rate = (
        (curr_price / prev_high) - 1
    ) * 100

    return {
        "price": curr_price,
        "ma20": ma20,
        "rsi": rsi,
        "drop_rate": drop_rate,
        "data_date": df.index[-1]
    }


# ============================================================
# [6. 전략 판단]
# ============================================================

ALLOC_MAP = {
    "PANIC_EXIT":
        "현금 100% (전량매도)",

    "SELL_83":
        "현금 70% : AGQ 15% : SLV 15%",

    "SELL_78":
        "현금 40% : AGQ 30% : SLV 30%",

    "NORMAL":
        "현금 10% : AGQ 45% : SLV 45%",

    "WAIT":
        "현금 40% : AGQ 20% : SLV 40%"
}


def get_strategy_tag(price, ma20, rsi, drop_rate, previous_tag):

    # --------------------------------------------------------
    # 1. 급락 방어
    # --------------------------------------------------------

    if drop_rate <= -10.0:
        return "PANIC_EXIT"

    # --------------------------------------------------------
    # 2. RSI 과열
    # --------------------------------------------------------

    if rsi >= 83:
        return "SELL_83"

    if rsi >= 78:
        return "SELL_78"

    # --------------------------------------------------------
    # 3. 추세 판단
    # --------------------------------------------------------

    if price > ma20 * 1.03:
        return "NORMAL"

    if price < ma20 * 0.97:
        return "WAIT"

    # --------------------------------------------------------
    # 4. ±3% 횡보구간
    # 이전 상태 유지
    # --------------------------------------------------------

    if previous_tag in ALLOC_MAP:
        return previous_tag

    return "WAIT"


# ============================================================
# [7. 한국 시간]
# ============================================================

def get_korea_time():
    return datetime.now(
        ZoneInfo(TIMEZONE)
    )


# ============================================================
# [8. 메시지 생성]
# ============================================================

def create_message(
    title,
    today_str,
    tag,
    alloc,
    data
):

    price = data["price"]
    ma20 = data["ma20"]
    rsi = data["rsi"]
    drop_rate = data["drop_rate"]

    return (
        f"{title}\n\n"
        f"📅 날짜: {today_str}\n"
        f"📊 현재 상태: {tag}\n"
        f"💡 권장 비중: {alloc}\n\n"
        f"------------------------\n"
        f"💰 현재가: ${price:.2f}\n"
        f"📊 MA20: ${ma20:.2f}\n"
        f"📈 RSI: {rsi:.1f}\n"
        f"📉 직전 고점 대비: {drop_rate:.1f}%\n"
        f"------------------------\n"
        f"🤖 SLV 전략 봇 정상 작동 중"
    )


# ============================================================
# [9. 메인]
# ============================================================

def main():

    state = load_state()

    try:

        # ----------------------------------------------------
        # 데이터
        # ----------------------------------------------------

        data = get_strategy_data()

        price = data["price"]
        ma20 = data["ma20"]
        rsi = data["rsi"]
        drop_rate = data["drop_rate"]

        # ----------------------------------------------------
        # 한국 시간
        # ----------------------------------------------------

        now = get_korea_time()

        today_str = now.strftime(
            "%Y-%m-%d"
        )

        current_hour = now.hour

        print(
            f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}]"
        )

        print(
            f"SLV=${price:.2f} | "
            f"MA20=${ma20:.2f} | "
            f"RSI={rsi:.1f} | "
            f"Drop={drop_rate:.1f}%"
        )

        # ----------------------------------------------------
        # 전략 판단
        # ----------------------------------------------------

        previous_tag = state.get(
            "last_tag",
            ""
        )

        tag = get_strategy_tag(
            price,
            ma20,
            rsi,
            drop_rate,
            previous_tag
        )

        alloc = ALLOC_MAP[tag]

        print(
            f"이전 상태: {previous_tag or '없음'}"
        )

        print(
            f"현재 상태: {tag}"
        )

        print(
            f"비중: {alloc}"
        )

        # ----------------------------------------------------
        # 조건 1
        # 전략 변경
        # ----------------------------------------------------

        is_changed = (
            previous_tag != tag
        )

        # ----------------------------------------------------
        # 조건 2
        # 아침 정기 보고
        #
        # 기존:
        # current_hour == 9
        #
        # 개선:
        # 9시 이후 첫 실행이면 보고
        #
        # 예:
        # 09:00 실행 → 보고
        # 09:15 실행 → 보고
        # 10:00 실행 → 보고
        #
        # 단, 하루에 한 번만
        # ----------------------------------------------------

        last_report_date = state.get(
            "last_report_date",
            ""
        )

        is_report_time = (
            current_hour >= 9
            and last_report_date != today_str
        )

        # ----------------------------------------------------
        # 알림
        # ----------------------------------------------------

        if is_changed or is_report_time:

            if is_changed:
                title = (
                    "🔄 [전략 변동 알림]"
                )
            else:
                title = (
                    "☀️ [아침 정기 보고 - 시스템 정상]"
                )

            msg = create_message(
                title,
                today_str,
                tag,
                alloc,
                data
            )

            success = send_msg(msg)

            if success:

                # 전략 상태 업데이트
                state["last_tag"] = tag

                # 정기 보고였다면 날짜 기록
                if is_report_time:
                    state["last_report_date"] = today_str

                save_state(state)

                print("상태 저장 완료")

            else:
                print(
                    "Telegram 전송 실패 → "
                    "상태를 변경하지 않습니다."
                )

        else:

            print(
                "알림 조건 없음 → "
                "메시지를 보내지 않습니다."
            )

            # 처음 실행하면서 상태가 비어있는 경우
            # 정상적인 전략 상태는 저장
            if not state.get("last_tag"):
                state["last_tag"] = tag
                save_state(state)

    except Exception as e:

        print(
            f"\n❌ 프로그램 오류: {type(e).__name__}"
        )

        print(f"상세 내용: {e}")


# ============================================================
# [10. 실행]
# ============================================================

if __name__ == "__main__":
    main()
