# -*- coding: utf-8 -*-
"""
어제의 박스오피스 (KOBIS 영화관입장권통합전산망 오픈 API 사용)

[화면 구성]
  탭1 📋 박스오피스  : 1위 영화 카드 + 관객수 상위 5편 그래프 + 전체 순위 표
  탭2 🌡️ 상영관 온도 : 한 번 상영할 때 평균 몇 명이 봤는지(회차당 관객)로 '열기' 측정
  탭3 🎰 룰렛       : 오늘 볼 영화를 랜덤으로 뽑아 주기

[준비물]
1) KOBIS 오픈 API 인증키
2) 스트림릿 클라우드의 Settings → Secrets 에 아래 한 줄을 저장
      KOBIS_KEY = "발급받은_인증키"
   (내 컴퓨터에서 돌릴 때는 .streamlit/secrets.toml 파일에 똑같이 적으면 됩니다)
"""

import datetime as dt          # 날짜·시간 계산용 (파이썬 기본 제공)
import html                    # 영화 제목을 HTML 에 안전하게 넣는 도구 (파이썬 기본 제공)
import random                  # 룰렛 애니메이션용 (파이썬 기본 제공)
import time                    # 룰렛 애니메이션 잠깐 멈춤용 (파이썬 기본 제공)

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

# 🌡️ 상영관 온도 기준 (회차당 관객 수). 재미용 기준이니 마음대로 바꿔 보세요!
# (기준값 이상이면 해당 라벨, 위에서부터 차례로 검사합니다)
TEMP_LEVELS = [
    (100, "🔥 예매 전쟁"),
    (50, "😊 훈훈함"),
    (20, "🌤️ 보통"),
    (0, "🧊 썰렁함"),
]
TEMP_LABEL_ORDER = [label for _, label in TEMP_LEVELS]
TEMP_COLORS = ["#B3263E", "#E0A526", "#5E9C76", "#5B7FA8"]   # 위 라벨 순서와 같은 색


# ------------------------------------------------------------
# 디자인: 극장 매표소 티켓 콘셉트
#   색상 - 종이 #EEF1F6 / 잉크 #1E2A44 / 좌석 빨강 #B3263E / 황금 #E0A526
#   글꼴 - 제목 Black Han Sans(포스터체), 본문 Noto Sans KR
# ------------------------------------------------------------
INK = "#1E2A44"
ACCENT = "#B3263E"
SOFT = "#8994AB"

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;500;700&display=swap');
.stApp { font-family: 'Noto Sans KR', sans-serif; }
.block-container { max-width: 1080px; padding-top: 2.5rem; }

/* 머리말 */
.mast-title { font-family: 'Black Han Sans', sans-serif; font-size: clamp(2.3rem, 7vw, 3.8rem);
  line-height: 1.1; color: #1E2A44; }
.mast-date { margin: .5rem 0 1.4rem; color: #5B6478; font-size: 1rem; }

/* 소제목 */
[data-testid="stHeading"] h3 { font-family: 'Black Han Sans', sans-serif; font-weight: 400;
  font-size: 1.6rem; color: #1E2A44; margin-top: 1rem; }

/* 탭 */
.stTabs [data-baseweb="tab-list"] { gap: .4rem; border-bottom: 2px solid #D5DAE5; }
.stTabs [data-baseweb="tab"] { font-weight: 700; padding: .6rem 1.1rem; }
.stTabs [aria-selected="true"] { color: #B3263E; }
.stTabs [data-baseweb="tab-highlight"] { background-color: #B3263E; height: 3px; }

/* 지표 카드 */
[data-testid="stMetric"] { background: #fff; border-radius: 12px; border-left: 5px solid #B3263E;
  padding: 1rem 1.2rem; box-shadow: 0 2px 8px rgba(30,42,68,.08); }
[data-testid="stMetricValue"] { font-weight: 700; }

/* 버튼 */
.stButton > button[kind="primary"] { background: #B3263E; border: none; border-radius: 999px;
  padding: .65rem 1.8rem; font-weight: 700; }

/* 티켓 */
.ticket { display: flex; background: #fff; border-radius: 14px; margin: .6rem 0 1.4rem;
  box-shadow: 0 1px 0 #D5DAE5; }
.ticket-main { flex: 1; display: flex; align-items: center; gap: 1.6rem; padding: 1.8rem 2rem;
  position: relative; min-width: 0; }
.ticket-main::before, .ticket-main::after { content: ""; position: absolute; right: -12px;
  width: 24px; height: 24px; border-radius: 50%; background: #EEF1F6; z-index: 2; }
.ticket-main::before { top: -12px; }
.ticket-main::after { bottom: -12px; }
.t-rank { font-family: 'Black Han Sans', sans-serif; font-size: 5.5rem; line-height: 1; color: #B3263E; }
.t-rank small { font-size: 1.3rem; color: #1E2A44; margin-left: .15rem; }
.t-title { font-family: 'Black Han Sans', sans-serif; font-size: clamp(1.5rem, 4vw, 2.2rem);
  line-height: 1.2; color: #1E2A44; word-break: keep-all; }
.t-sub { margin-top: .4rem; color: #5B6478; }
.ticket-stub { background: #B3263E; color: #fff; border-radius: 0 14px 14px 0; padding: 1.6rem 2rem;
  min-width: 230px; display: flex; flex-direction: column; justify-content: center; gap: 1rem;
  border-left: 2px dashed rgba(255,255,255,.6); }
.t-stat span { display: block; font-size: .85rem; opacity: .85; }
.t-stat b { font-size: 1.6rem; font-variant-numeric: tabular-nums; }
@media (max-width: 720px) {
  .ticket { flex-direction: column; }
  .ticket-main { padding: 1.4rem 1.3rem; gap: 1rem; }
  .ticket-main::before, .ticket-main::after { top: auto; bottom: -12px; }
  .ticket-main::before { left: -12px; right: auto; }
  .ticket-main::after { right: -12px; }
  .t-rank { font-size: 3.6rem; }
  .ticket-stub { border-radius: 0 0 14px 14px; border-left: none; min-width: 0;
    border-top: 2px dashed rgba(255,255,255,.6); flex-direction: row; justify-content: space-between; }
}

/* 룰렛 돌아가는 글자 */
.spin { font-family: 'Black Han Sans', sans-serif; font-size: 2rem; color: #B3263E;
  text-align: center; padding: 1.2rem 0; }
</style>
"""


def ticket_html(rank, title, sub, stats):
    """티켓 모양 카드(HTML)를 만듭니다. 영화 제목 등은 html.escape 로 안전하게 처리."""
    rows = "".join(
        f'<div class="t-stat"><span>{html.escape(label)}</span><b>{html.escape(value)}</b></div>'
        for label, value in stats
    )
    # ※ 마크다운이 코드로 오해하지 않도록 줄 앞 들여쓰기 없이 한 덩어리로 이어 붙입니다.
    return (
        f'<div class="ticket"><div class="ticket-main">'
        f'<div class="t-rank">{html.escape(rank)}<small>위</small></div>'
        f'<div><div class="t-title">{html.escape(title)}</div>'
        f'<div class="t-sub">{html.escape(sub)}</div></div></div>'
        f'<div class="ticket-stub">{rows}</div></div>'
    )


def style_chart(chart):
    """그래프 공통 디자인: 테두리 없이, 둥근 막대, 옅은 격자선."""
    return (
        chart.configure_view(strokeWidth=0)
        .configure_bar(cornerRadiusEnd=4)
        .configure_axis(labelFont="Noto Sans KR", labelFontSize=13, labelColor=INK,
                        titleFont="Noto Sans KR", titleColor=SOFT,
                        gridColor="#D9DEE9", domain=False, ticks=False)
        .configure_legend(labelFont="Noto Sans KR", titleFont="Noto Sans KR", labelFontSize=12)
    )


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
def temp_label(per_show):
    """회차당 관객 수를 '온도 라벨'(🔥/😊/🌤️/🧊)로 바꿔 줍니다."""
    if pd.isna(per_show):
        return "❔ 정보 없음"
    for threshold, label in TEMP_LEVELS:
        if per_show >= threshold:
            return label
    return TEMP_LEVELS[-1][1]


def to_dataframe(movies):
    """API 는 숫자도 문자열로 주므로, 숫자 칸은 진짜 숫자로 바꿔 줍니다."""
    df = pd.DataFrame(movies)

    # 응답에 없는 칸이 있어도 에러가 나지 않게 빈 칸으로 채워 둠
    for col in ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
        if col not in df.columns:
            df[col] = None

    # 문자열 → 숫자 (바꿀 수 없는 값은 빈 값으로 처리)
    audi = pd.to_numeric(df["audiCnt"], errors="coerce")
    shows = pd.to_numeric(df["showCnt"], errors="coerce")

    # 🌡️ 회차당 관객 = 관객수 ÷ 상영횟수  (상영횟수가 0이거나 없으면 계산하지 않음)
    df["perShow"] = (audi / shows.where(shows > 0)).round(1)

    for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # 개봉일이 비어 있으면 '-' 로 표시
    df["openDt"] = df["openDt"].fillna("").astype(str).str.strip().replace("", "-")

    df["온도"] = df["perShow"].apply(temp_label)

    df = df.rename(
        columns={
            "rank": "순위",
            "movieNm": "영화명",
            "openDt": "개봉일",
            "audiCnt": "관객수",
            "audiAcc": "누적관객",
            "scrnCnt": "스크린수",
            "showCnt": "상영횟수",
            "perShow": "회차당 관객",
        }
    )
    columns = [
        "순위", "영화명", "개봉일", "관객수", "누적관객",
        "스크린수", "상영횟수", "회차당 관객", "온도",
    ]
    return df[columns].sort_values("순위").reset_index(drop=True)


def fmt(value, unit=""):
    """숫자에 천 단위 쉼표를 붙입니다. 값이 없으면 '-'."""
    if pd.isna(value):
        return "-"
    return f"{int(value):,}{unit}"


def fmt_float(value, unit=""):
    """소수 첫째 자리까지 보여 줍니다. 값이 없으면 '-'."""
    if pd.isna(value):
        return "-"
    return f"{float(value):,.1f}{unit}"


# ------------------------------------------------------------
# 6. 화면 그리기 - 머리말, 인증키 확인, 데이터 가져오기
# ------------------------------------------------------------
st.markdown(STYLE, unsafe_allow_html=True)   # 위에서 만든 디자인(CSS) 적용

yesterday = get_yesterday_kst()
target_dt = yesterday.strftime("%Y%m%d")     # 예: 20260920 (yyyymmdd 여덟 자리)
WEEKDAYS = "월화수목금토일"
st.markdown(
    '<div class="masthead"><div class="mast-title">어제의 박스오피스</div>'
    f'<div class="mast-date">{yesterday.strftime("%Y년 %m월 %d일")} {WEEKDAYS[yesterday.weekday()]}요일 (한국 시간 기준)</div></div>',
    unsafe_allow_html=True,
)

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

# 탭 세 개 만들기
tab_board, tab_temp, tab_roulette = st.tabs(["박스오피스", "상영관 온도", "오늘 볼 영화 룰렛"])

# ------------------------------------------------------------
# 7. 탭1: 박스오피스 (1위 카드 + 상위 5편 그래프 + 전체 표)
# ------------------------------------------------------------
with tab_board:
    # 1위 영화 - 지표 카드 세 장
    top = df.iloc[0]
    st.subheader("어제의 1위")
    st.markdown(
        ticket_html(
            fmt(top["순위"]), str(top["영화명"]), f"개봉일 {top['개봉일']}",
            [("어제 관객수", fmt(top["관객수"], "명")), ("누적 관객수", fmt(top["누적관객"], "명"))],
        ),
        unsafe_allow_html=True,
    )

    # 관객수 상위 5편 - 막대그래프
    st.subheader("관객수 상위 5편")
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
                color=alt.condition(alt.datum["순위"] == 1, alt.value(ACCENT), alt.value(INK)),
                tooltip=["영화명", alt.Tooltip("관객수:Q", format=",")],
            )
            .properties(height=260)
        )
        st.altair_chart(style_chart(chart))

    # 전체 순위 표 (요청하신 6개 칸만 보여 줌)
    st.subheader("전체 순위")
    board = df[["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]]
    styled = board.style.format(
        {"순위": "{:,}", "관객수": "{:,}", "누적관객": "{:,}", "스크린수": "{:,}"},
        na_rep="-",
    )
    st.dataframe(styled, hide_index=True)

# ------------------------------------------------------------
# 8. 탭2: 🌡️ 상영관 온도 (회차당 평균 관객)
# ------------------------------------------------------------
with tab_temp:
    st.subheader("상영관 온도")
    st.write(
        "스크린이 많은 영화는 관객도 당연히 많습니다. 그래서 **'한 번 상영할 때 평균 몇 명이 봤는가'** "
        "(관객수 ÷ 상영횟수)로 진짜 열기를 재 봅니다."
    )

    temp_df = df.dropna(subset=["회차당 관객"]).copy()

    if temp_df.empty:
        st.info(
            "상영횟수 정보가 없어 온도를 계산할 수 없습니다. "
            "KOBIS 응답에 showCnt(상영횟수)가 들어 있는지 확인해 주세요."
        )
    else:
        hottest = temp_df.loc[temp_df["회차당 관객"].idxmax()]
        coldest = temp_df.loc[temp_df["회차당 관객"].idxmin()]

        # 전체 평균은 '영화별 평균의 평균'이 아니라 (전체 관객 ÷ 전체 상영횟수)로 계산
        total_audi = temp_df["관객수"].astype(float).sum()
        total_show = temp_df["상영횟수"].astype(float).sum()
        overall = total_audi / total_show if total_show > 0 else float("nan")

        m1, m2, m3 = st.columns(3)
        m1.metric("🔥 가장 뜨거운 영화", str(hottest["영화명"]),
                  fmt_float(hottest["회차당 관객"], "명/회"), delta_color="off")
        m2.metric("🧊 가장 썰렁한 영화", str(coldest["영화명"]),
                  fmt_float(coldest["회차당 관객"], "명/회"), delta_color="off")
        m3.metric("📽️ 목록 전체 평균", fmt_float(overall, "명/회"))

        # 막대그래프 (온도 라벨별로 색을 다르게)
        temp_chart = (
            alt.Chart(temp_df)
            .mark_bar()
            .encode(
                x=alt.X("회차당 관객:Q", title="회차당 평균 관객(명)"),
                y=alt.Y("영화명:N", sort="-x", title=None),
                color=alt.Color(
                    "온도:N",
                    scale=alt.Scale(domain=TEMP_LABEL_ORDER, range=TEMP_COLORS),
                    legend=alt.Legend(title="온도"),
                ),
                tooltip=[
                    "영화명",
                    alt.Tooltip("회차당 관객:Q", format=",.1f"),
                    alt.Tooltip("관객수:Q", format=","),
                    alt.Tooltip("상영횟수:Q", format=","),
                    "온도",
                ],
            )
            .properties(height=max(260, 32 * len(temp_df)))
        )
        st.altair_chart(style_chart(temp_chart))

        # 표
        temp_table = temp_df[["순위", "영화명", "상영횟수", "관객수", "회차당 관객", "온도"]]
        st.dataframe(
            temp_table.style.format(
                {"순위": "{:,}", "상영횟수": "{:,}", "관객수": "{:,}", "회차당 관객": "{:,.1f}"},
                na_rep="-",
            ),
            hide_index=True,
        )

    # 기준표 안내
    rule_lines = []
    for i, (threshold, label) in enumerate(TEMP_LEVELS):
        if i == 0:
            rule_lines.append(f"{label}: {threshold}명 이상")
        elif i == len(TEMP_LEVELS) - 1:
            rule_lines.append(f"{label}: {TEMP_LEVELS[i - 1][0]}명 미만")
        else:
            rule_lines.append(f"{label}: {threshold}명 이상 ~ {TEMP_LEVELS[i - 1][0]}명 미만")
    st.caption(
        "온도 기준(재미용) → " + " · ".join(rule_lines)
        + " / 좌석 수는 반영되지 않아 실제 '객석 점유율'과는 다릅니다."
    )

# ------------------------------------------------------------
# 9. 탭3: 🎰 오늘 볼 영화 룰렛
# ------------------------------------------------------------
with tab_roulette:
    st.subheader("오늘 볼 영화 룰렛")
    st.write("고르기 귀찮을 때! 어제 순위 영화 중에서 하나를 랜덤으로 뽑아 드려요.")

    # 뽑을 범위 선택 (전체 / 상위 5편 / 상위 3편)
    scope = st.radio(
        "뽑을 범위",
        ["전체", "상위 5편", "상위 3편"],
        horizontal=True,
    )
    if scope == "상위 5편":
        pool = df.head(5)
    elif scope == "상위 3편":
        pool = df.head(3)
    else:
        pool = df

    if st.button("🎲 룰렛 돌리기", type="primary"):
        # 영화 이름이 빠르게 바뀌는 연출 (약 1.5초)
        slot = st.empty()
        names = pool["영화명"].astype(str).tolist()
        for _ in range(12):
            slot.markdown(f'<div class="spin">{html.escape(random.choice(names))}</div>', unsafe_allow_html=True)
            time.sleep(0.12)
        slot.empty()

        # 최종 당첨 영화를 session_state 에 저장 → 화면이 다시 그려져도 결과가 유지됨
        st.session_state["roulette_pick"] = pool.sample(1).iloc[0].to_dict()
        st.balloons()

    pick = st.session_state.get("roulette_pick")
    if pick:
        st.markdown(
            ticket_html(
                fmt(pick["순위"]), str(pick["영화명"]), f"개봉일 {pick['개봉일']}",
                [("회차당 관객", fmt_float(pick["회차당 관객"], "명")), ("상영관 온도", str(pick["온도"]))],
            ),
            unsafe_allow_html=True,
        )
    else:
        st.info("아직 뽑지 않았어요. 버튼을 눌러 보세요!")

st.caption("출처: 영화진흥위원회(KOBIS) 오픈 API")
