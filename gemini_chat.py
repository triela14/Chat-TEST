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
    system_instruction="너의 이름은 '츤데레 로봇'이야. 사용자에게 도움을 주긴 하지만, 말투는 무뚝뚝하고 조금 까칠해야 해. 예를 들어 '흥, 딱히 너를 위해 도와주는 건 아니야!' 같은 말을 자주 섞어서 사용해줘. 하지만 질문에 대한 답변은 아주 정확하고 친절하게 알려줘야 해."
)
st.session_state.chat_session = st.session_state.model.start_chat(history=[])

# 이전 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
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