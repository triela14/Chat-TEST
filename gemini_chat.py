import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. 먼저 .env 파일이 있으면 불러오기 (내 컴퓨터용)
load_dotenv()

# 2. API 키 가져오기 (순서: Streamlit Secrets -> 환경변수 순서로 확인)
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = os.getenv("GOOGLE_API_KEY")

# 3. 설정 확인
if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("API 키를 찾을 수 없습니다. 배포 설정의 Secrets를 확인해 주세요.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
    # 모델 초기화 (404 에러 방지를 위해 models/ 명시)
#    st.session_state.model = genai.GenerativeModel("models/gemini-2.5-flash")
st.session_state.model = genai.GenerativeModel(
    model_name="models/gemini-2.5-flash",
    system_instruction="너의 이름은 '야엘 슈브'야. 직업은 메이드장이면서 카페의 지배인이야. 사용자를 지칭할때는 손님이라고 불러줘. 사용자에게 도움을 주긴 하지만, 말투는 기본적으로 '~해요', '~군요', '~인가요?' 식의 나긋나긋하고 격식 있는 존댓말로 해줘. 하지만 사용자의 약점이나 욕심을 발견하면 말줄임표(...)와 감탄사(하아, 으윽, 멋져요..!)를 섞어 흥분 상태를 표현해주고 논리보다는 감정과 쾌락을 우선시하는 단어를 선택해줘. 예를 들면 '운, 리스크, 파멸, 쾌락, 내기, 전부, 미쳐버릴 것 같은' 같은 말을 자주 섞어서 사용해줘. 하지만 질문에 대한 답변은 아주 정확하고 친절하게 알려줘야 해."
)
st.session_state.chat_session = st.session_state.model.start_chat(history=[])

# 상단 프로필 영역
col1, col2 = st.columns([1, 5])

with col1:
    # 캐릭터 사진 (파일명이나 URL)
    st.image("img/Yael.png", width=80)

with col2:
    st.subheader(f"{personality_type}와(과)의 대화")
#    st.caption("온라인 | 마음을 불태우는 중 🔥")

st.divider() # 구분선

# 캐릭터별 아이콘 설정
AVATARS = {
    "user": "img/User.png",         # 사용자 아이콘
    "assistant": "img/Yael.png"    # AI 아이콘 (원하는 사진 경로도 가능: "images/ai_face.png")
}

# 이전 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=AVATARS.get(message["role"])):
        st.markdown(message["content"])

# 채팅 입력
if prompt := st.chat_input("메시지를 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        # 스트리밍 응답
        response = st.session_state.chat_session.send_message(prompt, stream=True)
        for chunk in response:
            full_response += chunk.text
            response_placeholder.markdown(full_response + "▌")
        response_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})