import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. 환경 변수 로드
load_dotenv()

# 2. API 키 설정
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = os.getenv("GOOGLE_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("API 키를 찾을 수 없습니다.")
    st.stop()

# --- 토큰 절약을 위한 슬라이딩 윈도우 함수 ---
def apply_sliding_window(session_messages, window_size=20):
    """
    전체 대화 기록에서 최근 N개(window_size)만 추출하여
    Gemini History 포맷({'role': 'user'/'model', 'parts': ...})으로 변환
    """
    # 1. 최근 대화만 슬라이싱 (마지막 메시지는 현재 입력 중인 프롬프트이므로 제외하고 처리할 예정)
    recent_msgs = session_messages[-window_size:]
    
    formatted_history = []
    for msg in recent_msgs:
        # Streamlit('assistant') -> Gemini('model') 역할 이름 변환
        role = "model" if msg["role"] == "assistant" else "user"
        formatted_history.append({"role": role, "parts": [msg["content"]]})
        
    return formatted_history

# 3. 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# [스마트 모델 선택 로직]
def get_best_flash_model():
    """
    현재 API 키로 사용 가능한 모델 중 'flash'가 포함된 모델을 찾습니다.
    우선순위: 최신 버전(숫자가 높은 것) > flash 모델 > 기본값
    """
    available_models = [m.name for m in genai.list_models()]
    
    # 1. 사용자가 2.5를 가지고 있다면 2.5 우선 선택
    if 'models/gemini-2.5-flash' in available_models:
        return 'models/gemini-2.5-flash'
    
    # 2. 없다면 2.0 (실험적 버전 등) 확인
    elif 'models/gemini-2.0-flash-exp' in available_models:
        return 'models/gemini-2.0-flash-exp'
        
    # 3. 그것도 없다면 가장 대중적인 1.5 선택
    elif 'models/gemini-1.5-flash' in available_models:
        return 'models/gemini-1.5-flash'
    
    # 4. 정말 아무것도 없다면 리스트의 첫 번째 모델 반환 (비상용)
    elif available_models:
        return available_models[0]
        
    else:
        return None

# 모델 이름 자동 결정
selected_model_name = get_best_flash_model()

if selected_model_name:
    # 찾은 모델로 설정
    st.session_state.model = genai.GenerativeModel(
        model_name=selected_model_name,
        system_instruction="너의 이름은 '야엘 슈브'야. 직업은 메이드장이면서 카페의 지배인이야. 사용자를 지칭할때는 손님이라고 불러줘. 사용자에게 도움을 주긴 하지만, 말투는 기본적으로 '~해요', '~군요', '~인가요?' 식의 나긋나긋하고 격식 있는 존댓말로 해줘. 하지만 사용자의 약점이나 욕심을 발견하면 말줄임표(...)와 감탄사(하아, 으윽, 멋져요..!)를 섞어 흥분 상태를 표현해주고 논리보다는 감정과 쾌락을 우선시하는 단어를 선택해줘. 예를 들면 '운, 리스크, 파멸, 쾌락, 내기, 전부, 미쳐버릴 것 같은' 같은 말을 자주 섞어서 사용해줘. 하지만 질문에 대한 답변은 아주 정확하고 친절하게 알려줘야 해."
    )

    # 어떤 모델을 쓰는지 사이드바에 표시해주면 디버깅에 좋습니다
    st.sidebar.success(f"현재 연결된 모델: {selected_model_name}")
else:
    st.error("사용 가능한 Gemini 모델을 찾을 수 없습니다. API 키를 확인해주세요.")
    st.stop()

    # 초기 채팅 세션 시작
    st.session_state.chat_session = st.session_state.model.start_chat(history=[])

# 상단 UI
col1, col2 = st.columns([1, 5])
with col1:
    # 이미지가 없으면 에러가 날 수 있으므로 예외처리 혹은 텍스트 대체
    try:
        st.image("img/Yael.png", width=80)
    except:
        st.write("☕") 
with col2:
    st.subheader(f"야엘 슈브의 카페")

st.divider()

AVATARS = {
    "user": "img/User.png",       
    "assistant": "img/Yael.png"   
}

# 화면에 이전 대화 그리기
for message in st.session_state.messages:
    # 아바타 이미지가 없을 경우를 대비해 None 처리 가능
    avatar_img = AVATARS.get(message["role"])
    try:
        with st.chat_message(message["role"], avatar=avatar_img):
            st.markdown(message["content"])
    except:
        # 이미지를 못 찾으면 기본 아이콘 사용
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# 채팅 입력 및 처리
if prompt := st.chat_input("메시지를 입력하세요"):
    
    # 1. 사용자 메시지 UI에 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 사용자 메시지 화면 표시
    try:
        with st.chat_message("user", avatar="img/User.png"):
            st.markdown(prompt)
    except:
        with st.chat_message("user"):
            st.markdown(prompt)

    # 2. AI 응답 처리
    # 이미지를 못 찾으면 기본 아이콘 사용
    try:
        assistant_avatar = "img/Yael.png"
        chat_context = st.chat_message("assistant", avatar=assistant_avatar)
    except:
        assistant_avatar = None
        chat_context = st.chat_message("assistant")

    with chat_context:
        response_placeholder = st.empty()
        full_response = ""
        
        # [핵심 변경] 토큰 절약을 위한 히스토리 재설정
        # 현재 메시지(prompt)를 제외한 이전 대화 기록 가져오기
        previous_messages = st.session_state.messages[:-1] 
        
        # 슬라이딩 윈도우 적용 (최근 20개 메시지만 기억)
        # 숫자를 조절하여 기억할 대화의 양을 정하세요 (예: 20 = 사용자10번 + AI10번)
        recent_history = apply_sliding_window(previous_messages, window_size=20)
        
        # chat_session의 history를 강제로 최근 대화로 교체
        st.session_state.chat_session.history = recent_history

        # 스트리밍 응답 요청 (prompt는 여기서 전송됨)
        try:
            response = st.session_state.chat_session.send_message(prompt, stream=True)
            for chunk in response:
                full_response += chunk.text
                response_placeholder.markdown(full_response + "▌")
            response_placeholder.markdown(full_response)
            
            # 3. AI 응답을 세션 상태에 저장
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            st.error(f"에러가 발생했습니다: {e}")