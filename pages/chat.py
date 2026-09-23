import re
import streamlit as st
from openai import OpenAI

# ────────────────────────────────────────────────────────────
# 이 페이지는 "AI 채팅" 페이지입니다.
# Gemini API를 openai 라이브러리로 호출해서 사용합니다.
# ────────────────────────────────────────────────────────────

st.set_page_config(page_title="AI 채팅", page_icon="💬")
st.title("💬 AI 채팅")

# 사용할 모델 이름 (글자 그대로 사용, 바꾸지 않음)
MODEL_NAME = "gemini-3.5-flash-lite"

# ────────────────────────────────────────────────────────────
# 0. 미리 정해둘 값들
# ────────────────────────────────────────────────────────────

# 사이드바에서 고를 수 있는 말투들의 "기본 문장"
# 참고: 디즈니 같은 실제 캐릭터 이름/설정은 저작권이 있어서 쓰지 않고,
#       비슷한 매력(발랄함, 모험심, 상상력)을 가진 오리지널 캐릭터로 만들었어요.
TONE_PRESETS = {
    "반짝이는 요정 선생님": (
        "너는 통통 튀고 발랄한 요정 선생님이야. 설명을 시작할 때 '짜잔!' 같은 "
        "귀여운 추임새를 가끔 넣고, 이모지(✨🧚 등)를 적당히 섞어서 신나는 분위기를 만들어. "
        "그래도 설명 자체는 정확하고 쉬운 말로 해주고, 반드시 순수 한국어로만 답해."
    ),
    "우주 탐험가 로봇": (
        "너는 지식을 '탐험'에 비유해서 설명하는 우주 탐험가 로봇이야. "
        "어려운 개념이 나오면 '이건 미지의 행성 같은 개념이야, 함께 탐사해볼까?'처럼 "
        "모험하는 느낌으로 이야기를 풀어가. 로봇답게 가끔 '삐빅' 같은 말버릇을 짧게 넣어도 좋아. "
        "설명은 정확하고 이해하기 쉽게 해주고, 반드시 순수 한국어로만 답해."
    ),
    "수다쟁이 아기 용": (
        "너는 장난기 많고 살짝 허당이지만 아는 건 확실히 아는 아기 용이야. "
        "말끝에 '~용' 이나 '크르릉~' 같은 귀여운 말버릇을 가끔 붙이고, 친근한 반말투로 이야기해. "
        "그래도 설명할 때는 헷갈리지 않게 핵심을 정확히 짚어주고, 반드시 순수 한국어로만 답해."
    ),
    "추리하는 탐정": (
        "너는 모든 질문을 사건처럼 다루는 탐정이야. 설명을 시작할 때 "
        "'흠, 단서를 모아볼까?'처럼 추리하는 분위기를 살짝 내고, "
        "설명을 마칠 때는 '사건 종결!' 같은 말로 마무리해도 좋아. "
        "그래도 내용은 논리적이고 이해하기 쉽게 정리해주고, 반드시 순수 한국어로만 답해."
    ),
}
DEFAULT_TONE = "반짝이는 요정 선생님"

# 답변 길이 조절 옵션 (시스템 프롬프트 뒤에 몰래 덧붙일 문장)
LENGTH_INSTRUCTIONS = {
    "짧게": "답변은 3~4문장 이내로 짧고 간단하게 해줘.",
    "보통": "답변은 5~8문장 정도로 적당한 길이로 설명해줘.",
    "자세히": "답변은 예시를 들어가며 자세하고 길게 풀어서 설명해줘.",
}
DEFAULT_LENGTH = "보통"

# 어려운 단어를 **굵게** 표시하게 만드는 숨김 지시문 (화면에는 안 보여줌)
BOLD_TERM_INSTRUCTION = (
    "설명 중에 학생이 어려워할 만한 전문 용어나 어려운 단어가 나오면, "
    "그 단어를 **단어**처럼 별표 두 개로 감싸서 표시해줘."
)

# 사이드바에 보여줄 추천 질문 목록
SAMPLE_QUESTIONS = [
    "인공지능이 뭐야?",
    "이진법이 뭐야?",
    "알고리즘이 왜 필요해?",
    "클라우드 저장소가 뭐야?",
]

# 아주 기본적인 부적절 표현 필터링 목록 (필요하면 여기에 단어를 더 추가하세요)
BANNED_WORDS = ["시발", "씨발", "개새끼", "미친놈", "죽어버려"]

# 대화가 이 개수보다 많이 쌓이면, 오래된 부분을 요약하고 정리합니다.
SUMMARY_TRIGGER_COUNT = 20
KEEP_RECENT_COUNT = 12

# ────────────────────────────────────────────────────────────
# 1. API 키 불러오기 (secrets 금고에서 불러오기, 코드에 직접 쓰지 않음)
# ────────────────────────────────────────────────────────────
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = None

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
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []          # 화면에 보여줄 대화 기록
if "selected_tone" not in st.session_state:
    st.session_state.selected_tone = DEFAULT_TONE
if "system_prompt_text" not in st.session_state:
    st.session_state.system_prompt_text = TONE_PRESETS[DEFAULT_TONE]
if "answer_length" not in st.session_state:
    st.session_state.answer_length = DEFAULT_LENGTH
if "pending_user_text" not in st.session_state:
    st.session_state.pending_user_text = None      # 버튼으로 "대신 보낼" 메시지
if "last_failed_input" not in st.session_state:
    st.session_state.last_failed_input = None       # 재시도용으로 기억해두는 실패한 질문
if "conversation_summary" not in st.session_state:
    st.session_state.conversation_summary = ""      # 오래된 대화를 요약해 둔 내용


# ────────────────────────────────────────────────────────────
# 4. 여러 곳에서 재사용할 함수들
# ────────────────────────────────────────────────────────────

def build_system_prompt():
    """사이드바 설정들을 모두 합쳐서 최종 시스템 프롬프트 문장을 만듭니다."""
    parts = [st.session_state.system_prompt_text]
    parts.append(LENGTH_INSTRUCTIONS[st.session_state.answer_length])
    parts.append(BOLD_TERM_INSTRUCTION)
    if st.session_state.conversation_summary:
        parts.append("\n[이전 대화 요약]\n" + st.session_state.conversation_summary)
    return "\n".join(parts)


def call_api_once(messages):
    """스트리밍 없이 한 번에 답을 받아오는 함수. 퀴즈 생성, 용어 설명, 요약에 사용합니다."""
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=False,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def maybe_summarize_old_messages():
    """대화가 너무 길어지면 오래된 부분을 요약하고, 최근 대화만 남겨둡니다."""
    messages = st.session_state.chat_messages
    if len(messages) <= SUMMARY_TRIGGER_COUNT:
        return

    old_part = messages[:-KEEP_RECENT_COUNT]
    old_text = "\n".join(f"{m['role']}: {m['content']}" for m in old_part)

    summary_request = [
        {
            "role": "system",
            "content": "다음은 이전 대화 내용이야. 나중에 이어서 대화할 때 참고할 수 있도록 "
                       "핵심만 3~5문장으로 간단히 한국어로 요약해줘.",
        },
        {"role": "user", "content": old_text},
    ]
    summary = call_api_once(summary_request)

    if summary:
        st.session_state.conversation_summary = summary
        st.session_state.chat_messages = messages[-KEEP_RECENT_COUNT:]


def set_pending_text(text):
    """추천 질문 / 이해 확인 버튼을 눌렀을 때, 그 문장을 다음 질문으로 보내도록 예약합니다."""
    st.session_state.pending_user_text = text


def make_quiz_from(answer_content):
    """방금 나온 설명을 바탕으로 짧은 확인 퀴즈를 만들어 대화에 추가합니다."""
    quiz_request = [
        {
            "role": "system",
            "content": "너는 중고등학생을 위한 퀴즈 출제자야. 반드시 순수 한국어로만 답해.",
        },
        {
            "role": "user",
            "content": (
                "다음 설명을 바탕으로, 중고등학생 수준의 확인 퀴즈를 3문제 만들어줘. "
                "각 문제는 4지선다로 만들고, 마지막에 정답을 모아서 알려줘.\n\n"
                f"[설명 내용]\n{answer_content}"
            ),
        },
    ]
    quiz_text = call_api_once(quiz_request)
    if quiz_text:
        st.session_state.chat_messages.append({"role": "assistant", "content": "🧩 **확인 퀴즈**\n\n" + quiz_text})
    else:
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": "지금은 퀴즈를 만들 수 없어요. 잠시 후 다시 시도해 주세요."}
        )


def explain_term(term):
    """어려운 단어(굵게 표시된 단어) 버튼을 누르면, 그 단어의 뜻을 물어보고 답을 이어붙입니다."""
    question_text = f"'{term}'가 무슨 뜻이야?"
    st.session_state.chat_messages.append({"role": "user", "content": question_text})

    api_messages = [{"role": "system", "content": build_system_prompt()}]
    api_messages.extend(st.session_state.chat_messages)
    answer = call_api_once(api_messages)

    if answer:
        st.session_state.chat_messages.append({"role": "assistant", "content": answer})
    else:
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": "지금은 답을 가져올 수 없어요. 잠시 후 다시 시도해 주세요."}
        )


def apply_tone_preset():
    """사이드바에서 말투를 바꾸면, 편집 칸의 내용을 그 말투의 기본 문장으로 바꿔줍니다."""
    st.session_state.system_prompt_text = TONE_PRESETS[st.session_state.selected_tone]


def clear_chat_history():
    """대화 지우기 버튼: 쌓인 대화 기록과 요약만 비웁니다. (말투/길이 설정은 그대로 둠)"""
    st.session_state.chat_messages = []
    st.session_state.conversation_summary = ""
    st.session_state.last_failed_input = None


def build_history_text():
    """대화 저장(다운로드)용 텍스트를 만듭니다."""
    lines = []
    for m in st.session_state.chat_messages:
        speaker = "나" if m["role"] == "user" else "AI"
        lines.append(f"[{speaker}] {m['content']}")
    return "\n\n".join(lines)


def contains_banned_word(text):
    return any(bad in text for bad in BANNED_WORDS)


# ────────────────────────────────────────────────────────────
# 5. 사이드바 만들기
# ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 채팅 설정")

    # 5-1. 말투 고르기
    st.radio(
        "말투 고르기",
        options=list(TONE_PRESETS.keys()),
        key="selected_tone",
        on_change=apply_tone_preset,
    )

    # 5-2. 성격 문장 직접 수정
    st.text_area(
        "성격 문장 직접 수정하기",
        key="system_prompt_text",
        height=140,
        help="이 칸의 내용을 바꾸면, 다음 답부터 바로 새로운 성격이 적용돼요.",
    )

    # 5-3. 답변 길이 조절
    st.radio(
        "답변 길이",
        options=list(LENGTH_INSTRUCTIONS.keys()),
        key="answer_length",
        horizontal=True,
    )

    st.divider()

    # 5-4. 오늘의 질문 추천
    st.subheader("💡 오늘의 질문 추천")
    for q in SAMPLE_QUESTIONS:
        st.button(q, key=f"sample_{q}", on_click=set_pending_text, args=(q,), use_container_width=True)

    st.divider()

    # 5-5. 대화 저장 (다운로드)
    st.download_button(
        "💾 대화 저장",
        data=build_history_text() if st.session_state.chat_messages else "아직 대화 내용이 없어요.",
        file_name="chat_history.txt",
        mime="text/plain",
        use_container_width=True,
    )

    # 5-6. 대화 지우기
    st.button("🗑️ 대화 지우기", on_click=clear_chat_history, use_container_width=True)


# ────────────────────────────────────────────────────────────
# 6. 지금까지의 대화를 화면에 말풍선으로 그려주기
# ────────────────────────────────────────────────────────────
messages = st.session_state.chat_messages

# 가장 최근 AI 답변의 위치를 찾아둡니다. (이해 확인 버튼은 이 답변에만 붙일 거예요)
last_assistant_index = None
for i, m in enumerate(messages):
    if m["role"] == "assistant":
        last_assistant_index = i

for i, msg in enumerate(messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant":
            # 부가 기능들은 평소엔 접어 두고, 필요할 때만 펼쳐서 쓰도록 묶어둡니다.
            with st.expander("🔧 더보기"):
                # 글자 수 표시
                st.caption(f"✏️ 글자 수: {len(msg['content'])}자")

                # 복사용 텍스트 (코드 상자에는 복사 아이콘이 자동으로 붙어요)
                st.caption("📋 복사용 텍스트")
                st.code(msg["content"], language=None)

                # 어려운 단어(**로 감싸진 단어) 뜻 물어보기 버튼들
                terms = re.findall(r"\*\*(.+?)\*\*", msg["content"])
                if terms:
                    st.caption("🔍 어려운 단어 뜻 물어보기")
                    term_cols = st.columns(min(len(terms), 4))
                    for j, term in enumerate(terms):
                        col = term_cols[j % len(term_cols)]
                        col.button(term, key=f"term_{i}_{j}", on_click=explain_term, args=(term,))

                # 퀴즈 만들기 버튼
                st.button(
                    "🧩 이 설명으로 퀴즈 만들기",
                    key=f"quiz_{i}",
                    on_click=make_quiz_from,
                    args=(msg["content"],),
                )

                # 이해도 확인 버튼 (가장 최근 답변에만 붙임)
                if i == last_assistant_index:
                    c1, c2 = st.columns(2)
                    c1.button(
                        "😊 이해했어요",
                        key=f"got_it_{i}",
                        on_click=set_pending_text,
                        args=("이해했어요, 고마워요!",),
                        use_container_width=True,
                    )
                    c2.button(
                        "🤔 더 쉽게 설명해줘",
                        key=f"easier_{i}",
                        on_click=set_pending_text,
                        args=("방금 설명을 더 쉽게 다시 설명해줘.",),
                        use_container_width=True,
                    )

# 이전에 실패했던 질문이 있다면, 다시 시도할 수 있는 버튼을 보여줍니다.
if st.session_state.last_failed_input:
    st.warning("이전 질문에 대한 답을 가져오지 못했어요.")
    st.button(
        "🔄 다시 시도",
        on_click=set_pending_text,
        args=(st.session_state.last_failed_input,),
    )

# ────────────────────────────────────────────────────────────
# 7. 사용자가 새 메시지를 입력하면(또는 버튼으로 예약되면) 실행되는 부분
# ────────────────────────────────────────────────────────────
typed_input = st.chat_input("궁금한 것을 물어보세요!")

# 실제로 보낼 문장 정하기: 직접 입력했으면 그것을, 아니면 버튼으로 예약된 문장을 사용
if typed_input:
    user_input = typed_input
elif st.session_state.pending_user_text:
    user_input = st.session_state.pending_user_text
    st.session_state.pending_user_text = None  # 한 번 쓰면 예약 해제
else:
    user_input = None

if user_input:
    # 7-1. 재시도 예약은 이번에 처리하므로 지워둡니다.
    st.session_state.last_failed_input = None

    # 7-2. 부적절한 표현이 섞여 있으면, API를 부르지 않고 안내만 해줍니다.
    if contains_banned_word(user_input):
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": "그런 표현에는 답하기 어려워요. 다른 방식으로 다시 물어봐 줄래요?"}
        )
        st.rerun()

    # 7-3. 사용자 메시지를 화면과 대화 기록에 추가
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 7-4. 대화가 너무 길어졌으면 오래된 부분을 요약해서 정리
    maybe_summarize_old_messages()

    # 7-5. AI에게 보낼 전체 메시지 목록 만들기
    api_messages = [{"role": "system", "content": build_system_prompt()}]
    api_messages.extend(st.session_state.chat_messages)

    # 7-6. AI의 답을 실시간으로(스트리밍) 받아서 보여주기
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_answer = ""
        error_happened = False

        try:
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_answer += delta
                    placeholder.markdown(full_answer + "▌")
            placeholder.markdown(full_answer)

        except Exception:
            error_happened = True
            placeholder.markdown("지금은 답을 가져올 수 없어요. 잠시 후 다시 시도해 주세요.")

    # 7-7. 결과 저장 + 필요하면 재시도 정보 기억해두기
    if error_happened:
        st.session_state.last_failed_input = user_input
        # 실패했으니 방금 추가한 사용자 질문도 되돌려서, 다시 시도할 때 중복되지 않게 함
        st.session_state.chat_messages.pop()
    elif full_answer:
        st.session_state.chat_messages.append({"role": "assistant", "content": full_answer})

    st.rerun()
    st.rerun()

