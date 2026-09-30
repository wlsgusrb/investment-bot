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
# [1] 사용자 설정
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

STATE_FILE = "portfolio_state.json"

TICKER = "SLV"
TIMEZONE = "Asia/Seoul"

DOWNLOAD_PERIOD = "40d"
DOWNLOAD_INTERVAL = "1d"

# ============================================================
# [2] 기본 검증
# ============================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "TELEGRAM_TOKEN 환경변수가 설정되지 않았습니다."
    )

if not TELEGRAM_CHAT_ID:
    raise RuntimeError(
        "TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다."
    )

# ============================================================
# [3] Telegram 메시지 전송
# ============================================================

def send_msg(msg, max_retries=3):
    token = (os.getenv("TELEGRAM_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    if not token:
        print("Telegram 전송 실패: TELEGRAM_TOKEN이 비어 있습니다.")
        return False

    if not chat_id:
        print("Telegram 전송 실패: TELEGRAM_CHAT_ID가 비어 있습니다.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": msg
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                url,
                data=payload,
                timeout=15
            )

            try:
                result = response.json()
            except ValueError:
                result = {}

            if response.status_code == 200 and result.get("ok") is True:
                print("Telegram 메시지 전송 성공")
                return True

            description = result.get(
                "description",
                "응답 설명 없음"
            )

            print(
                f"Telegram 전송 실패 "
                f"({attempt}/{max_retries}): "
                f"HTTP {response.status_code}"
            )

            print(
                f"Telegram API error: {description}"
            )

        except requests.RequestException as e:
            print(
                f"Telegram 전송 실패 "
                f"({attempt}/{max_retries}): "
                f"{type(e).__name__}: {e}"
            )

        except Exception as e:
            print(
                f"Telegram 처리 오류: "
                f"{type(e).__name__}: {e}"
            )

        if attempt < max_retries:
            time.sleep(2)

    print("Telegram 전송 최종 실패")
    return False

# ============================================================
# [4] 상태 파일
# ============================================================

DEFAULT_STATE = {
    "last_tag": "",
    "last_report_date": ""
}


def load_state():
    if not os.path.exists(STATE_FILE):
        return DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        if not isinstance(state, dict):
            return DEFAULT_STATE.copy()

        return {
            "last_tag": state.get("last_tag", ""),
            "last_report_date": state.get(
                "last_report_date", ""
            )
        }

    except (OSError, json.JSONDecodeError) as e:
        print(f"상태 파일 읽기 오류: {e}")
        return DEFAULT_STATE.copy()


def save_state(state):
    temp_file = STATE_FILE + ".tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                state,
                f,
                ensure_ascii=False,
                indent=2
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_file, STATE_FILE)
        return True

    except Exception as e:
        print(f"상태 파일 저장 오류: {e}")

        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except OSError:
            pass

        return False

# ============================================================
# [5] 시장 데이터 가져오기
# ============================================================

def get_strategy_data():
    print(f"{TICKER} 데이터 다운로드 중...")

    df = yf.download(
        TICKER,
        period=DOWNLOAD_PERIOD,
        interval=DOWNLOAD_INTERVAL,
        progress=False,
        auto_adjust=False,
        threads=False,
        timeout=20
    )

    if df is None or df.empty:
        raise ValueError(
            "Yahoo Finance 데이터가 비어 있습니다."
        )

    # MultiIndex 컬럼 처리
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance의 일반적인 형식:
        # ('Close', 'SLV') 또는 ('SLV', 'Close')
        if "Close" in df.columns.get_level_values(0):
            df.columns = df.columns.get_level_values(0)
        elif "Close" in df.columns.get_level_values(-1):
            df.columns = df.columns.get_level_values(-1)
        else:
            raise ValueError(
                f"Close 컬럼을 찾을 수 없습니다: {df.columns}"
            )

    required_columns = ["Close", "High"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(
                f"필수 데이터 '{col}'가 없습니다."
            )

    df = df[required_columns].copy()

    for col in required_columns:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    df = df.dropna(
        subset=["Close", "High"]
    ).copy()

    df = df.sort_index()

    if len(df) < 20:
        raise ValueError(
            f"분석 데이터 부족: {len(df)}개"
        )

    if (df["Close"] <= 0).any():
        raise ValueError("비정상적인 종가가 포함되어 있습니다.")

    # --------------------------------------------------------
    # MA20
    # --------------------------------------------------------

    df["MA20"] = (
        df["Close"]
        .rolling(window=20, min_periods=20)
        .mean()
    )

    # --------------------------------------------------------
    # RSI 14 (SMA 방식)
    # --------------------------------------------------------

    delta = df["Close"].diff()

    gain = (
        delta.clip(lower=0)
        .rolling(window=14, min_periods=14)
        .mean()
    )

    loss = (
        (-delta.clip(upper=0))
        .rolling(window=14, min_periods=14)
        .mean()
    )

    df["RSI"] = float("nan")

    normal = (loss > 0) & (gain > 0)
    only_gain = (loss == 0) & (gain > 0)
    only_loss = (gain == 0) & (loss > 0)
    no_change = (gain == 0) & (loss == 0)

    rs = gain[normal] / loss[normal]

    df.loc[normal, "RSI"] = (
        100 - (100 / (1 + rs))
    )

    df.loc[only_gain, "RSI"] = 100
    df.loc[only_loss, "RSI"] = 0
    df.loc[no_change, "RSI"] = 50

    # --------------------------------------------------------
    # 최신 지표 검증
    # --------------------------------------------------------

    latest = df.iloc[-1]

    if pd.isna(latest["MA20"]):
        raise ValueError("MA20 계산 결과가 NaN입니다.")

    if pd.isna(latest["RSI"]):
        raise ValueError("RSI 계산 결과가 NaN입니다.")

    if len(df) < 2:
        raise ValueError("직전 거래일 데이터가 없습니다.")

    # --------------------------------------------------------
    # 현재값
    # --------------------------------------------------------

    curr_price = float(latest["Close"])
    ma20 = float(latest["MA20"])
    rsi = float(latest["RSI"])

    prev_high = float(df["High"].iloc[-2])

    if prev_high <= 0:
        raise ValueError("직전 고가가 비정상적입니다.")

    drop_rate = (
        (curr_price / prev_high) - 1
    ) * 100

    data_date = df.index[-1]

    return {
        "price": curr_price,
        "ma20": ma20,
        "rsi": rsi,
        "drop_rate": drop_rate,
        "data_date": data_date
    }

# ============================================================
# [6] 전략 판단
# ============================================================

ALLOC_MAP = {
    "PANIC_EXIT": "현금 100% (전량매도)",
    "SELL_83": "현금 70% : AGQ 15% : SLV 15%",
    "SELL_78": "현금 40% : AGQ 30% : SLV 30%",
    "NORMAL": "현금 10% : AGQ 45% : SLV 45%",
    "WAIT": "현금 40% : AGQ 20% : SLV 40%"
}


def get_strategy_tag(
    price, ma20, rsi, drop_rate, previous_tag
):
    # 1. 급락 방어
    if drop_rate <= -10.0:
        return "PANIC_EXIT"

    # 2. RSI 과열
    if rsi >= 83:
        return "SELL_83"

    if rsi >= 78:
        return "SELL_78"

    # 3. 추세 판단
    if price > ma20 * 1.03:
        return "NORMAL"

    if price < ma20 * 0.97:
        return "WAIT"

    # 4. 횡보구간: 이전 상태 유지
    if previous_tag in ALLOC_MAP:
        return previous_tag

    return "WAIT"

# ============================================================
# [7] 한국 시간
# ============================================================

def get_korea_time():
    return datetime.now(ZoneInfo(TIMEZONE))

# ============================================================
# [8] 메시지 생성
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
    data_date = data["data_date"]

    return (
        f"{title}\n\n"
        f"📅 알림 날짜: {today_str}\n"
        f"📆 데이터 날짜: {data_date}\n"
        f"📊 현재 상태: {tag}\n"
        f"💡 전략 비중: {alloc}\n\n"
        f"------------------------\n"
        f"💰 현재가: ${price:.2f}\n"
        f"📊 MA20: ${ma20:.2f}\n"
        f"📈 RSI: {rsi:.1f}\n"
        f"📉 직전 거래일 고가 대비: "
        f"{drop_rate:.1f}%\n"
        f"------------------------\n"
        f"🤖 SLV 전략 봇 정상 작동 중"
    )

# ============================================================
# [9] 메인
# ============================================================

def main():
    state = load_state()

    try:
        # 데이터
        data = get_strategy_data()

        price = data["price"]
        ma20 = data["ma20"]
        rsi = data["rsi"]
        drop_rate = data["drop_rate"]

        # 한국 시간
        now = get_korea_time()
        today_str = now.strftime("%Y-%m-%d")
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

        # 전략 판단
        previous_tag = state.get("last_tag", "")

        tag = get_strategy_tag(
            price,
            ma20,
            rsi,
            drop_rate,
            previous_tag
        )

        alloc = ALLOC_MAP[tag]

        print(f"이전 상태: {previous_tag or '없음'}")
        print(f"현재 상태: {tag}")
        print(f"비중: {alloc}")

        # 알림 조건
        is_changed = previous_tag != tag

        last_report_date = state.get(
            "last_report_date", ""
        )

        is_report_time = (
            current_hour >= 9
            and last_report_date != today_str
        )

        # 처음 실행 시 상태가 없는 경우
        # 전략 변경 알림 대신 기준 상태만 저장
        if not previous_tag:
            state["last_tag"] = tag

            if not save_state(state):
                print("초기 상태 저장에 실패했습니다.")

            print(
                "최초 실행: 현재 전략을 기준 상태로 저장합니다."
            )

            # 첫 실행도 오전 9시 이후라면 정기 보고
            if is_report_time:
                msg = create_message(
                    "☀️ [아침 정기 보고 - 시스템 정상]",
                    today_str,
                    tag,
                    alloc,
                    data
                )

                if send_msg(msg):
                    state["last_report_date"] = today_str
                    if not save_state(state):
                        print("보고 날짜 저장 실패")
                else:
                    print("정기 보고 전송 실패")

            return

        # 전략 변경 또는 정기 보고
        if is_changed or is_report_time:
            if is_changed:
                title = "🔄 [전략 변동 알림]"
            else:
                title = "☀️ [아침 정기 보고 - 시스템 정상]"

            msg = create_message(
                title,
                today_str,
                tag,
                alloc,
                data
            )

            success = send_msg(msg)

            if success:
                state["last_tag"] = tag

                if is_report_time:
                    state["last_report_date"] = today_str

                if save_state(state):
                    print("상태 저장 완료")
                else:
                    print(
                        "상태 저장 실패: "
                        "다음 실행에서 중복 알림이 발생할 수 있습니다."
                    )
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

    except Exception as e:
        print(
            f"\n❌ 프로그램 오류: {type(e).__name__}"
        )
        print(f"상세 내용: {e}")


# ============================================================
# [10] 실행
# ============================================================

if __name__ == "__main__":
    main()
