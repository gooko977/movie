# -*- coding: utf-8 -*-
"""
어제의 박스오피스 (KOBIS 영화관입장권통합전산망 오픈 API 사용)

[준비물]
1) KOBIS 오픈 API 인증키
2) 스트림릿 클라우드의 Settings → Secrets 에 아래 한 줄을 저장
      KOBIS_KEY = "발급받은_인증키"
   (내 컴퓨터에서 돌릴 때는 .streamlit/secrets.toml 파일에 똑같이 적으면 됩니다)
"""

import datetime as dt          # 날짜·시간 계산용 (파이썬 기본 제공)

import altair as alt           # 막대그래프용 (스트림릿과 함께 설치됨)
import pandas as pd            # 표 데이터 다루기
import requests                # 인터넷으로 API 요청 보내기 (스트림릿과 함께 설치됨)
import streamlit as st         # 웹 앱 만들기

# ------------------------------------------------------------
# 1. 기본 설정
# ------------------------------------------------------------
st.set_page_config(page_title="어제의 박스오피스", page_icon="🎬", layout="wide")

# KOBIS 일별 박스오피스 요청 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 한국 표준시(UTC+9). 한국은 서머타임이 없어서 +9시간 고정으로 충분합니다.
# 배포 서버의 시계는 한국 시간이 아니므로, 서버 시계를 그대로 쓰면 안 됩니다.
KST = dt.timezone(dt.timedelta(hours=9))


class BoxOfficeError(Exception):
    """API 요청이 잘못됐을 때 쓰는 오류 (화면에 보여 줄 한국어 안내문을 담음)"""


class EmptyBoxOffice(BoxOfficeError):
    """요청은 성공했지만 영화 목록이 비어 있을 때 쓰는 오류"""


# ------------------------------------------------------------
# 2. 어제 날짜 계산 (한국 시간 기준)
# ------------------------------------------------------------
def get_yesterday_kst():
    """지금 한국 시간에서 하루를 빼서 '어제' 날짜를 돌려줍니다."""
    now_kst = dt.datetime.now(KST)               # 서버 시계와 상관없이 한국의 지금 시각
    return (now_kst - dt.timedelta(days=1)).date()


# ------------------------------------------------------------
# 3. 인증키 불러오기 (코드에 직접 쓰지 않고 secrets 에서만 읽음)
# ------------------------------------------------------------
def load_api_key():
    """secrets 에서 KOBIS_KEY 를 읽어옵니다. 없으면 None."""
    try:
        key = str(st.secrets["KOBIS_KEY"]).strip()
    except Exception:
        return None
    return key or None


# ------------------------------------------------------------
# 4. API 호출 (10분 동안 결과를 기억해서 불필요한 재요청을 줄임)
#    ※ 오류가 나면 기억하지 않으므로, 고친 뒤 새로고침하면 바로 반영됩니다.
# ------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner="박스오피스 정보를 불러오는 중...")
def fetch_box_office(api_key, target_dt):
    """KOBIS 에서 특정 날짜의 일별 박스오피스 목록(리스트)을 가져옵니다."""
    try:
        resp = requests.get(
            API_URL,
            params={"key": api_key, "targetDt": target_dt},
            timeout=10,  # 10초 안에 답이 없으면 포기
        )
    except requests.exceptions.Timeout:
        # ※ 오류 원문을 화면에 그대로 찍지 않습니다. (주소에 인증키가 섞여 있을 수 있음)
        raise BoxOfficeError(
            "KOBIS 서버의 응답이 너무 늦습니다. 잠시 후 다시 시도해 주세요."
        ) from None
    except requests.exceptions.RequestException:
        raise BoxOfficeError(
            "KOBIS 서버에 연결하지 못했습니다. 인터넷 연결이나 KOBIS 서비스 "
            "점검 여부를 확인해 주세요."
        ) from None

    # HTTP 상태코드가 200(정상)이 아닌 경우
    if resp.status_code != 200:
        raise BoxOfficeError(
            f"KOBIS 서버가 오류 코드({resp.status_code})를 돌려줬습니다. "
            "잠시 후 다시 시도해 주세요."
        )

    # 응답이 JSON 형식이 아닌 경우 (점검 페이지 등)
    try:
        data = resp.json()
    except ValueError:
        raise BoxOfficeError(
            "KOBIS 응답을 해석할 수 없습니다. 서비스 점검 중일 수 있으니 "
            "잠시 후 다시 시도해 주세요."
        ) from None

    if not isinstance(data, dict):
        raise BoxOfficeError("KOBIS 응답의 형식이 예상과 다릅니다.")

    # ★ 인증키가 틀려도 상태코드는 200 이고, 대신 faultInfo 상자가 옵니다.
    if "faultInfo" in data:
        fault = data["faultInfo"]
        message = fault.get("message", "") if isinstance(fault, dict) else ""
        raise BoxOfficeError(
            "KOBIS 가 요청을 거절했습니다. 인증키(KOBIS_KEY)가 올바른지, "
            "승인·사용 가능 상태인지 확인해 주세요."
            + (f"\n\nKOBIS 안내 메시지: {message}" if message else "")
        )

    # 정상 응답이면 boxOfficeResult → dailyBoxOfficeList 안에 영화 목록이 있음
    result = data.get("boxOfficeResult")
    movies = result.get("dailyBoxOfficeList") if isinstance(result, dict) else None

    if movies is None:
        raise BoxOfficeError("KOBIS 응답에 박스오피스 항목이 없습니다.")
    if not isinstance(movies, list) or len(movies) == 0:
        raise EmptyBoxOffice("영화 목록이 비어 있습니다.")

    return movies


# ------------------------------------------------------------
# 5. 응답을 보기 좋은 표(DataFrame)로 바꾸기
# ------------------------------------------------------------
def to_dataframe(movies):
    """API 는 숫자도 문자열로 주므로, 숫자 칸은 진짜 숫자로 바꿔 줍니다."""
    df = pd.DataFrame(movies)

    # 응답에 없는 칸이 있어도 에러가 나지 않게 빈 칸으로 채워 둠
    for col in ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]:
        if col not in df.columns:
            df[col] = None

    # 문자열 → 숫자 (바꿀 수 없는 값은 빈 값으로 처리)
    for col in ["rank", "audiCnt", "audiAcc", "scrnCnt"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # 개봉일이 비어 있으면 '-' 로 표시
    df["openDt"] = df["openDt"].fillna("").astype(str).str.strip().replace("", "-")

    df = df.rename(
        columns={
            "rank": "순위",
            "movieNm": "영화명",
            "openDt": "개봉일",
            "audiCnt": "관객수",
            "audiAcc": "누적관객",
            "scrnCnt": "스크린수",
        }
    )
    columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
    return df[columns].sort_values("순위").reset_index(drop=True)


def fmt(value, unit=""):
    """숫자에 천 단위 쉼표를 붙입니다. 값이 없으면 '-'."""
    if pd.isna(value):
        return "-"
    return f"{int(value):,}{unit}"


# ------------------------------------------------------------
# 6. 화면 그리기
# ------------------------------------------------------------
st.title("🎬 어제의 박스오피스")

yesterday = get_yesterday_kst()
target_dt = yesterday.strftime("%Y%m%d")     # 예: 20260920 (yyyymmdd 여덟 자리)
st.caption(f"조회 기준일: {yesterday.strftime('%Y년 %m월 %d일')} (한국 시간 기준 어제)")

# (1) 인증키 확인
api_key = load_api_key()
if api_key is None:
    st.error("인증키(KOBIS_KEY)를 찾을 수 없습니다.")
    st.markdown(
        "**확인해 보세요**\n"
        "1. 스트림릿 클라우드 앱 화면에서 **Settings → Secrets** 를 엽니다.\n"
        "2. 아래 한 줄이 들어 있는지 확인하고, 없으면 추가한 뒤 저장합니다.\n"
        "3. 저장 후 앱을 새로고침(또는 Reboot) 합니다.\n\n"
        "```toml\nKOBIS_KEY = \"발급받은_인증키\"\n```\n"
        "내 컴퓨터에서 실행 중이라면 `.streamlit/secrets.toml` 파일에 같은 줄을 적어 주세요."
    )
    st.stop()  # 여기서 멈춤 (아래 코드는 실행하지 않음)

# (2) 데이터 가져오기 - 실패하면 빈 화면 대신 안내문을 보여 줌
try:
    movies = fetch_box_office(api_key, target_dt)
except EmptyBoxOffice:
    st.warning("어제의 영화 목록이 비어 있습니다.")
    st.markdown(
        "**확인해 보세요**\n"
        "- KOBIS 의 집계가 아직 끝나지 않았을 수 있습니다. 잠시 뒤 새로고침해 보세요.\n"
        "- KOBIS 사이트(kobis.or.kr)에서 같은 날짜의 박스오피스가 조회되는지 확인해 보세요.\n"
        "- 인증키 발급 상태나 일일 호출 한도도 함께 확인해 보세요."
    )
    st.stop()
except BoxOfficeError as e:
    st.error("박스오피스 정보를 불러오지 못했습니다.")
    st.markdown(str(e))
    st.markdown(
        "**확인해 보세요**\n"
        "- Secrets 의 `KOBIS_KEY` 가 정확한지 (앞뒤 공백·따옴표 포함)\n"
        "- KOBIS 서비스가 점검 중은 아닌지\n"
        "- 잠시 후 새로고침하면 해결되는지"
    )
    st.stop()
except Exception:
    # 예상하지 못한 오류. 원문을 그대로 보여 주면 민감한 정보가 섞일 수 있어 생략합니다.
    st.error("예상하지 못한 오류가 발생했습니다.")
    st.markdown(
        "**확인해 보세요**\n"
        "- 잠시 후 새로고침해 보세요.\n"
        "- 계속되면 스트림릿 클라우드의 **Manage app → Logs** 에서 오류 내용을 확인해 주세요."
    )
    st.stop()

df = to_dataframe(movies)

# (3) 1위 영화 - 지표 카드 세 장
top = df.iloc[0]
st.subheader("🥇 1위 영화")
c1, c2, c3 = st.columns(3)
c1.metric("영화명", str(top["영화명"]))
c2.metric("어제 관객수", fmt(top["관객수"], "명"))
c3.metric("누적 관객수", fmt(top["누적관객"], "명"))

# (4) 관객수 상위 5편 - 막대그래프
st.subheader("📊 관객수 상위 5편")
top5 = df.dropna(subset=["관객수"]).nlargest(5, "관객수").copy()
top5["관객수"] = top5["관객수"].astype(int)    # 그래프용으로 일반 정수로 변환

if top5.empty:
    st.info("관객수 정보가 없어 그래프를 그릴 수 없습니다.")
else:
    chart = (
        alt.Chart(top5)
        .mark_bar()
        .encode(
            x=alt.X("관객수:Q", title="관객수(명)"),
            y=alt.Y("영화명:N", sort="-x", title=None),   # 관객수 많은 순서로 위에서부터
            tooltip=["영화명", alt.Tooltip("관객수:Q", format=",")],
        )
        .properties(height=260)
    )
    st.altair_chart(chart, use_container_width=True)

# (5) 전체 순위 표
st.subheader("📋 전체 순위")
styled = df.style.format(
    {
        "순위": "{:,}",
        "관객수": "{:,}",
        "누적관객": "{:,}",
        "스크린수": "{:,}",
    },
    na_rep="-",
)
st.dataframe(styled, hide_index=True, use_container_width=True)

st.caption("출처: 영화진흥위원회(KOBIS) 오픈 API")
