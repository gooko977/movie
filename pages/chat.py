import streamlit as st
from openai import OpenAI

# ────────────────────────────────────────────────────────────
# 이 페이지는 "AI 채팅" 페이지입니다.
# Gemini API를 openai 라이브러리로 호출해서 사용합니다.
# (Gemini는 OpenAI 호환 주소를 제공해서 openai 라이브러리로 그대로 쓸 수 있어요)
# ────────────────────────────────────────────────────────────

st.set_page_config(page_title="AI 채팅", page_icon="💬")
st.title("💬 AI 채팅")

# 사용할 모델 이름 (글자 그대로 사용, 바꾸지 않음)
MODEL_NAME = "gemini-3.5-flash-lite"

# AI의 성격(시스템 프롬프트)을 정해줍니다.
# 이 문장은 화면에 절대 보여주지 않고, AI에게만 몰래 전달됩니다.
SYSTEM_PROMPT = (
    "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. "
    "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해"
)

# ────────────────────────────────────────────────────────────
# 1. API 키 불러오기 (secrets 금고에서 불러오기, 코드에 직접 쓰지 않음)
# ────────────────────────────────────────────────────────────
# secrets.toml 파일 안에 아래처럼 적혀 있어야 합니다.
# GEMINI_API_KEY = "여기에_본인_키"
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = None

# API 키가 없으면 안내 문구만 보여주고 아래 채팅 기능은 멈춥니다.
if not api_key:
    st.error("AI 채팅을 사용할 수 없어요. 관리자에게 API 키 설정을 확인해 달라고 요청해 주세요.")
    st.stop()

# ────────────────────────────────────────────────────────────
# 2. OpenAI 라이브러리로 Gemini 서버에 접속할 클라이언트 만들기
# ────────────────────────────────────────────────────────────
client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# ────────────────────────────────────────────────────────────
# 3. 이전 대화 기억하기 (st.session_state에 대화 기록 저장)
# ────────────────────────────────────────────────────────────
# messages 라는 이름으로 대화 기록을 저장해 둡니다.
# 새로고침하기 전까지는 계속 기억합니다.
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []  # 화면에 보여줄 대화 기록 (system 프롬프트는 제외)

# ────────────────────────────────────────────────────────────
# 4. 지금까지의 대화를 화면에 말풍선으로 그려주기
# ────────────────────────────────────────────────────────────
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ────────────────────────────────────────────────────────────
# 5. 사용자가 새 메시지를 입력하면 실행되는 부분
# ────────────────────────────────────────────────────────────
user_input = st.chat_input("궁금한 것을 물어보세요!")

if user_input:
    # 5-1. 사용자 메시지를 화면과 대화 기록에 추가
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 5-2. AI에게 보낼 전체 메시지 목록 만들기
    #      (맨 앞에 성격 설정을 몰래 넣고, 그 뒤에 실제 대화 기록을 이어붙임)
    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    api_messages.extend(st.session_state.chat_messages)

    # 5-3. AI의 답을 실시간으로(스트리밍) 받아서 보여주기
    with st.chat_message("assistant"):
        placeholder = st.empty()  # 글자가 채워질 빈 공간
        full_answer = ""          # 지금까지 도착한 답을 계속 이어붙일 변수
        error_happened = False

        try:
            # stream=True로 설정하면 답이 한 번에 오지 않고 조금씩 흘러들어옵니다.
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages,
                stream=True,
            )

            for chunk in stream:
                # chunk 안에 새로 도착한 글자 조각이 들어있습니다.
                delta = chunk.choices[0].delta.content
                if delta:
                    full_answer += delta
                    # 커서처럼 보이는 "▌" 을 뒤에 붙여서 타이핑 중인 느낌을 줍니다.
                    placeholder.markdown(full_answer + "▌")

            # 스트리밍이 끝나면 커서 없이 최종 답을 보여줍니다.
            placeholder.markdown(full_answer)

        except Exception:
            # 오류 화면을 그대로 보여주지 않고, 한국어 안내 문구만 보여줍니다.
            error_happened = True
            placeholder.markdown("지금은 답을 가져올 수 없어요. 잠시 후 다시 시도해 주세요.")

    # 5-4. AI의 답도 대화 기록에 저장해서 다음 질문에서 기억하도록 함
    #      (오류가 났을 때는 잘못된 답을 기억하지 않도록 저장하지 않음)
    if not error_happened and full_answer:
        st.session_state.chat_messages.append({"role": "assistant", "content": full_answer})
