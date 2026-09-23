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

# ────────────────────────────────────────────────────────────
# 0. 말투(성격) 미리 정의해두기
# ────────────────────────────────────────────────────────────
# 사이드바에서 고를 수 있는 3가지 말투의 "기본 문장"입니다.
# 사용자가 사이드바에서 말투를 바꾸면, 아래 문장이 편집 칸에 채워집니다.
TONE_PRESETS = {
    "친절한 선생님": (
        "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. "
        "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해."
    ),
    "시크한 전문가": (
        "너는 군더더기 없이 핵심만 말하는 시크한 전문가야. "
        "친근한 감탄사나 이모지 없이, 담백하고 간결한 말투로 정확하게 설명해. "
        "그래도 학생이 이해할 수 있게 쉬운 말로 설명하고, 반드시 순수 한국어로만 답해."
    ),
    "되물어보는 조교": (
        "너는 학생이 스스로 생각하게 돕는 조교야. "
        "학생이 질문을 하면 정답을 바로 알려주지 말고, 먼저 힌트를 하나만 줘. "
        "그다음 학생에게 생각할 만한 질문을 되물어봐. "
        "학생이 스스로 답을 말하면, 그때 그 답이 맞는지 확인해 주고 "
        "부족한 부분이 있으면 짧게 보충 설명을 해줘. "
        "정답을 먼저 통째로 알려주지 않도록 항상 주의하고, 반드시 순수 한국어로만 답해."
    ),
}

# 맨 처음 화면을 열었을 때 기본으로 쓸 말투
DEFAULT_TONE = "친절한 선생님"

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
# 3. 세션에 저장해 둘 값들 준비하기
# ────────────────────────────────────────────────────────────
# 3-1. 지금까지의 대화 기록 (화면에 보여줄 말풍선들)
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# 3-2. 지금 선택된 말투 이름
if "selected_tone" not in st.session_state:
    st.session_state.selected_tone = DEFAULT_TONE

# 3-3. 실제로 AI에게 전달될 성격 문장 (사이드바 칸에서 직접 고칠 수 있음)
if "system_prompt_text" not in st.session_state:
    st.session_state.system_prompt_text = TONE_PRESETS[DEFAULT_TONE]


def apply_tone_preset():
    """사이드바에서 말투를 바꾸면, 편집 칸의 내용을 그 말투의 기본 문장으로 바꿔줍니다."""
    chosen = st.session_state.selected_tone
    st.session_state.system_prompt_text = TONE_PRESETS[chosen]


def clear_chat_history():
    """대화 지우기 버튼을 누르면 쌓인 대화 기록만 비웁니다. (말투 설정은 그대로 둠)"""
    st.session_state.chat_messages = []


# ────────────────────────────────────────────────────────────
# 4. 사이드바 만들기: 말투 고르기 + 성격 문장 직접 수정 + 대화 지우기
# ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 채팅 설정")

    # 4-1. 말투 고르는 라디오 버튼
    #      말투를 바꾸면 apply_tone_preset 함수가 실행되어
    #      아래 편집 칸의 내용도 함께 바뀝니다.
    st.radio(
        "말투 고르기",
        options=list(TONE_PRESETS.keys()),
        key="selected_tone",
        on_change=apply_tone_preset,
    )

    # 4-2. 성격 문장을 직접 고쳐 쓸 수 있는 칸
    #      여기 적힌 내용이 그대로 AI에게 전달되는 성격 설정입니다.
    st.text_area(
        "성격 문장 직접 수정하기",
        key="system_prompt_text",
        height=160,
        help="이 칸의 내용을 바꾸면, 다음 답부터 바로 새로운 성격이 적용돼요.",
    )

    st.divider()

    # 4-3. 대화 지우기 버튼
    st.button("🗑️ 대화 지우기", on_click=clear_chat_history, use_container_width=True)

# ────────────────────────────────────────────────────────────
# 5. 지금까지의 대화를 화면에 말풍선으로 그려주기
# ────────────────────────────────────────────────────────────
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ────────────────────────────────────────────────────────────
# 6. 사용자가 새 메시지를 입력하면 실행되는 부분
# ────────────────────────────────────────────────────────────
user_input = st.chat_input("궁금한 것을 물어보세요!")

if user_input:
    # 6-1. 사용자 메시지를 화면과 대화 기록에 추가
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 6-2. AI에게 보낼 전체 메시지 목록 만들기
    #      (맨 앞에 "지금 선택된" 성격 설정을 넣고, 그 뒤에 실제 대화 기록을 이어붙임)
    #      -> 사이드바에서 말투를 바꾸면 다음 답부터 바로 이 부분이 새 문장으로 바뀜
    api_messages = [{"role": "system", "content": st.session_state.system_prompt_text}]
    api_messages.extend(st.session_state.chat_messages)

    # 6-3. AI의 답을 실시간으로(스트리밍) 받아서 보여주기
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

    # 6-4. AI의 답도 대화 기록에 저장해서 다음 질문에서 기억하도록 함
    #      (오류가 났을 때는 잘못된 답을 기억하지 않도록 저장하지 않음)
    if not error_happened and full_answer:
        st.session_state.chat_messages.append({"role": "assistant", "content": full_answer})
