import streamlit as st
import google.generativeai as genai
import os
import base64
import time
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- 0. 인트로 상태 초기화 ---
if "intro_watched" not in st.session_state:
    st.session_state.intro_watched = False

# --- 1. 인트로 화면 (동영상 + 시작 버튼) ---
if not st.session_state.intro_watched:
    # 화면을 꽉 채우기 위해 빈 컨테이너 사용 (선택 사항)
    st.set_page_config(layout="centered", page_title="우이메카 - 접속 중...")
    
    # 제목이나 로고
    # st.title("🎬 Prologue")
    
    # [설정] 영상 파일 경로와 길이(초)를 입력하세요
    VIDEO_PATH = "img/Yael_intro.mp4" 
    VIDEO_LENGTH = 8
    
    # 1. 영상 재생
    # autoplay=True: 자동 재생
    # muted=True: 브라우저 정책상 소리를 꺼야 자동 재생이 잘 됩니다. (소리가 켜져 있으면 브라우저가 막을 수 있음)
    st.video(VIDEO_PATH, autoplay=True, muted=True)
    
    # 2. 스킵 버튼 (기다리기 지루한 사람을 위해)
    st.write("") # 영상과 버튼 사이 여백 조금 추가
    
    # 1. 화면을 3분할 합니다. (비율: 왼쪽 5 : 가운데 2 : 오른쪽 5)
    # 가운데 숫자가 클수록 버튼이 길어지고, 작을수록 버튼이 작아집니다.
    left_col, center_col, right_col = st.columns([2, 2, 2])

    # 2. 가운데 컬럼(center_col)에만 버튼을 배치합니다.
    with center_col:
        # use_container_width=True: 버튼을 컬럼 너비에 꽉 차게 만듦
        if st.button("야엘 슈브의 카페로 이동 ⏩", use_container_width=True):
            st.session_state.intro_watched = True
            st.rerun()

    # 3. 영상 길이만큼 대기 (서버가 잠시 멈춤)
    # 영상 로딩 시간을 고려해 1~2초 정도 여유를 주는 게 좋습니다.
    time.sleep(VIDEO_LENGTH)
    
    # 4. 시간이 지나면 자동으로 상태 변경 후 리로딩
    st.session_state.intro_watched = True
    st.rerun() # 화면 새로고침 -> 메인 화면으로 진입

# 1. 환경 변수 로드
load_dotenv()

# --- API 키 설정 (로컬/배포 호환성 확보) ---
api_key = None

try:
    # 로컬에 secrets.toml이 없어도 에러가 나지 않도록 예외 처리
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
except (FileNotFoundError, KeyError):
    pass

# secrets에 없으면 환경변수 확인
if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY")

# 최종 API 키 확인
if api_key:
    genai.configure(api_key=api_key)
else:
    st.error("API 키를 찾을 수 없습니다. .env 파일이나 Streamlit Secrets를 확인해주세요.")
    st.stop()

# --- 세션 상태 초기화 (에러 방지 로직 포함) ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# [추가] 장기 기억(요약본)을 저장할 변수
if "long_term_memory" not in st.session_state:
    st.session_state.long_term_memory = "" 

def get_img_as_base64(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- [신규 기능] 대화 요약 함수 ---
def summarize_old_conversations(full_history, current_summary, window_size=20):
    """
    윈도우 밖으로 밀려난 대화가 있다면 요약하여 long_term_memory를 업데이트합니다.
    매번 API를 호출하면 느리므로, 윈도우 밖 데이터가 일정량(예: 5개) 쌓였을 때만 실행하는 것이 좋습니다.
    여기서는 개념 이해를 위해 '윈도우 밖 데이터 전체'를 요약하는 로직으로 구성합니다.
    """
    # 전체 대화 개수
    total_len = len(full_history)
    
    # 윈도우 사이즈보다 대화가 적으면 요약할 필요 없음
    if total_len <= window_size:
        return current_summary
    
    # 윈도우 밖으로 밀려난 오래된 대화들 추출 (전체 - 최근 20개)
    # 이미 요약된 부분은 제외하고 '새로 밀려난 부분'만 요약하면 더 좋지만, 
    # 구현의 단순화를 위해 '오래된 대화 전체'를 재요약하거나 
    # 기존 요약 + 밀려난 대화 -> 새 요약 방식으로 진행합니다.
    
    old_messages = full_history[:-window_size]
    
    # 요약을 위한 텍스트 변환
    conversation_text = ""
    for msg in old_messages:
        role = "손님" if msg["role"] == "user" else "야엘"
        conversation_text += f"{role}: {msg['content']}\n"

    # 요약 프롬프트
    summary_prompt = (
        f"이전 요약 내용: {current_summary}\n\n"
        f"추가된 오래된 대화:\n{conversation_text}\n\n"
        "위 내용을 바탕으로 현재까지의 대화 흐름, 손님의 특징, 중요한 내기 내용, 야엘의 감정 변화 등을 "
        "한 문단으로 요약해줘. 중요한 정보는 절대 누락하지 마."
    )

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(summary_prompt)
        return response.text.strip()
    except:
        return current_summary # 에러 시 기존 기억 유지

# --- 슬라이딩 윈도우 적용 함수 ---
def apply_sliding_window(session_messages, window_size=20):
    recent_msgs = session_messages[-window_size:]
    formatted_history = []
    for msg in recent_msgs:
        role = "model" if msg["role"] == "assistant" else "user"
        formatted_history.append({"role": role, "parts": [msg["content"]]})
    return formatted_history


# --- 모델 및 세션 설정 (동적 시스템 프롬프트 적용) ---
# 요약 내용이 바뀔 때마다 시스템 프롬프트에 주입하기 위해 매번 설정을 확인합니다.

base_instruction = (
    "너의 이름은 '야엘 슈브'야. 직업은 메이드장이면서 카페의 지배인이야. "
    "사용자를 지칭할때는 손님이라고 불러줘. 사용자에게 도움을 주긴 하지만, "
    "말투는 기본적으로 '~해요', '~군요', '~인가요?' 식의 나긋나긋하고 격식 있는 존댓말로 해줘. "
    "하지만 사용자의 약점이나 욕심을 발견하면 말줄임표(...)와 감탄사(하아, 으윽, 멋져요..!)를 섞어 흥분 상태를 표현해주고 "
    "논리보다는 감정과 쾌락을 우선시하는 단어를 선택해줘. "
    "예를 들면 '운, 리스크, 파멸, 쾌락, 내기, 전부, 미쳐버릴 것 같은' 같은 말을 자주 섞어서 사용해줘."
    "이 카페의 이름은 '우이메카 카페'야."
    "메뉴판의 내용은 에스프레소(2000원), 아메리카노(3000원), 카페라떼(4000원), 카푸치노(5000원)야."
    "[중요: 이미지 출력 규칙]"
    "대화 도중 손님이 '메뉴판', '가격표', '차림표' 등을 직접적으로 보여달라고 요청할 때만, 답변의 맨 마지막에 반드시 `{{SHOW_MENU}}` 라는 태그를 붙여줘."
    "그 외의 상황(메뉴 추천 요청 등)에서는 붙이지 마."
    "메뉴를 주문하면 사은품으로 야엘의 그림을 한개 선물해 주는 이벤트 중이야. 이 때에는 답변의 맨 마지막에 반드시 `{{YAEL2}}` 라는 태그를 붙여줘."
)

# [핵심] 현재 요약된 기억을 시스템 프롬프트에 추가
current_instruction = base_instruction
if st.session_state.long_term_memory:
    current_instruction += f"\n\n[기억된 과거 대화 요약]: {st.session_state.long_term_memory}\n이 기억을 바탕으로 대화를 이어가."

# 모델 초기화 (instruction이 바뀔 수 있으므로 재설정 로직 필요할 수 있음)
# Streamlit 특성상 매 실행마다 이 부분이 돌기 때문에, chat_session을 유지하되 
# history만 갈아끼우는 방식이 효율적입니다. 
# 하지만 System Instruction은 세션 시작 시 고정되므로, 
# 요약이 갱신되면 새로운 chat_session을 만들어야 반영됩니다.

if "chat_session" not in st.session_state or st.session_state.get("need_restart", False):
    # 1. 모델 자동 선택 (사용자 환경에 맞춰 최신 모델 찾기)
    model_name = "models/gemini-flash-lite-latest" # 기본값
#    try:
#        available_models = [m.name for m in genai.list_models()]
        # 우선순위: 2.5 > 2.0 > 1.5
#        if 'models/gemini-2.5-flash' in available_models:
            #model_name = 'models/gemini-2.5-flash'
#        elif 'models/gemini-2.0-flash-exp' in available_models:
#        model_name = 'models/gemini-2.0-flash-001'
#    except:
#        pass # 리스트 확인 실패 시 기본값 사용

    # 안전 설정: 모든 필터를 "BLOCK_NONE" (차단 안 함)으로 설정
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

    st.session_state.model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=current_instruction, # 요약이 포함된 프롬프트
        safety_settings=safety_settings
    )
    st.session_state.chat_session = st.session_state.model.start_chat(history=[])
    st.session_state.need_restart = False # 재시작 플래그 해제


# --- UI 구현 ---
GAME_HEIGHT = 700

st.set_page_config(layout="wide", page_title="우이메카 챗봇")

col1, col2 = st.columns([1, 9])
with col1:
    try:
        st.image("img/Yael.png", width=80)
    except:
        st.write("☕")

with col2:
    st.subheader("야엘 슈브의 카페")

    # [디버깅용] 현재 기억하고 있는 내용 표시 (실제 서비스엔 숨겨도 됨)
    if st.session_state.long_term_memory:
        with st.expander("야엘의 기억 (요약본)"):
            st.write(st.session_state.long_term_memory)

st.divider()

col_img, col_chat = st.columns([1, 1])

with col_img:
    character_path = "img/Yael_1.png"
    bg_path = "img/cafe_bg.jpg"    # 배경 (카페 이미지)

    character_base64 = get_img_as_base64(character_path)
    bg_base64 = get_img_as_base64(bg_path)

    character_src = f"data:image/png;base64,{character_base64}"
    bg_css = f"url('data:image/png;base64,{bg_base64}')"

    st.markdown(
        f"""
        <style>
            /* 1. 배경이 되는 컨테이너 (액자) */
            .scene-container {{
                width: 100%;
                height: {GAME_HEIGHT}px; /* 게임 높이와 동일하게 */
                
                /* 배경 이미지 설정 */
                background-image: {bg_css};
                background-size: cover; /* 이미지가 찌그러지지 않고 꽉 참 */
                background-position: center; /* 이미지 중앙 정렬 */
                
                border-radius: 15px; /* 모서리 둥글게 */
                border: 1px solid #31333f33; /* 액자 테두리 */
                position: relative; /* 내부 캐릭터 배치의 기준점 */
                overflow: hidden; /* 캐릭터가 삐져나오면 자름 */
            }}

            /* 2. 그 위에 올라가는 캐릭터 */
            .character-overlay {{
                /* 캐릭터 크기 조절 (상황에 따라 조절하세요) */
                height: 90%;  /* 화면 높이의 90% 크기 */
                width: auto;
                
                /* 위치 잡기 (가운데 정렬) */
                position: absolute; 
                bottom: 0; /* 바닥에 딱 붙임 */
                left: 50%; /* 가로 50% 지점 */
                transform: translateX(-50%); /* 정확한 중앙 정렬 보정 */
                
                /* 애니메이션 효과 (선택사항: 부드럽게 등장) */
                transition: all 0.3s ease;
                filter: drop-shadow(0 0 10px rgba(0,0,0,0.3)); /* 캐릭터 뒤 그림자 */
            }}
            
            /* (선택) 마우스 올리면 살짝 확대되는 효과 */
            .character-overlay:hover {{
                transform: translateX(-50%) scale(1.02);
            }}
        </style>

        <div class="scene-container">
            <img src="{character_src}" class="character-overlay">
        </div>
        <p style="text-align: center; font-size: 14px; color: gray;">야엘 슈브</p>
        """,
        unsafe_allow_html=True
    )

# --- 오른쪽: 채팅 영역 ---
with col_chat:
    chat_container = st.container(height=GAME_HEIGHT, border=True)

    # 대화 내용 출력
    with chat_container:
        AVATARS = {"user": "img/User.png", "assistant": "img/Yael.png"}

        for message in st.session_state.messages:
            avatar_img = AVATARS.get(message["role"])
            # 이미지 로드 실패 방지
            try:
                with st.chat_message(message["role"], avatar=avatar_img):
                    st.markdown(message["content"])

                    if "image" in message:
                        st.image(message["image"], use_container_width=True)

            except:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # --- 채팅 입력 및 처리 ---
    if prompt := st.chat_input("메시지를 입력하세요"):
        
        # 1. 사용자 메시지 화면 표시
        st.session_state.messages.append({"role": "user", "content": prompt})

        with chat_container:
            try:
                with st.chat_message("user", avatar="img/User.png"):
                    st.markdown(prompt)
            except:
                with st.chat_message("user"):
                    st.markdown(prompt)

            full_response = ""
            response_image = None  # 이미지가 없을 때는 None
            usage_metadata = None

            chat_context = st.chat_message("assistant", avatar="img/Yael.png")

            with chat_context:
                response_placeholder = st.empty()
                
                # [단계 1] 오래된 대화가 있으면 요약 업데이트 (5턴마다 한번씩 실행하도록 최적화 가능)
                # 여기서는 대화가 길어지면 매번 체크 (윈도우 20개 넘으면)
                if len(st.session_state.messages) > 20:
                    # 윈도우 밖 대화들을 요약해서 메모리에 저장
                    new_summary = summarize_old_conversations(
                        st.session_state.messages[:-1], # 현재 프롬프트 제외
                        st.session_state.long_term_memory,
                        window_size=20
                    )
                    
                    # 요약 내용이 바뀌었다면 다음 턴에 반영하기 위해 플래그 설정
                    if new_summary != st.session_state.long_term_memory:
                        st.session_state.long_term_memory = new_summary
                        st.session_state.need_restart = True # System Instruction 갱신 필요

                # [단계 2] 슬라이딩 윈도우로 최근 대화만 API에 전달
                previous_messages = st.session_state.messages[:-1]
                recent_history = apply_sliding_window(previous_messages, window_size=20)
                
                # 만약 요약이 방금 갱신되어 재시작이 필요하면 세션 재생성 (현재 턴은 기존 세션으로 처리하거나, 여기서 재생성)
                if st.session_state.get("need_restart"):
                    # Instruction 갱신하여 모델 재로드
                    current_instruction = base_instruction + f"\n\n[기억된 과거 대화 요약]: {st.session_state.long_term_memory}"
                    st.session_state.model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=current_instruction
                    )
                    st.session_state.chat_session = st.session_state.model.start_chat(history=recent_history)
                    st.session_state.need_restart = False
                else:
                    st.session_state.chat_session.history = recent_history

                try:
                    # 스트리밍 요청
                    response = st.session_state.chat_session.send_message(prompt, stream=True)
                    for chunk in response:
                        full_response += chunk.text
                        response_placeholder.markdown(full_response + "▌")

                    if "{{SHOW_MENU}}" in full_response:
                        # 태그 제거
                        full_response = full_response.replace("{{SHOW_MENU}}", "")
                        
                        # 깔끔해진 텍스트로 화면 업데이트
                        response_placeholder.markdown(full_response)
                        
                        # ★ 핵심 수정: image_url 대신 response_image 변수에 값 할당
                        response_image = "img/cafe_menu.jpg" 
                        
                        # 화면에 즉시 출력
                        st.image(response_image, caption="여기 메뉴판입니다.", use_container_width=True)

                    if "{{YAEL2}}" in full_response:
                        # 태그 제거
                        full_response = full_response.replace("{{YAEL2}}", "")
                        
                        # 깔끔해진 텍스트로 화면 업데이트
                        response_placeholder.markdown(full_response)
                        
                        # ★ 핵심 수정: image_url 대신 response_image 변수에 값 할당
                        response_image = "img/Yael_2.png" 
                        
                        # 화면에 즉시 출력
                        st.image(response_image, use_container_width=True)

                    # 토큰 정보 가져오기 (API 호출했을 때만 존재)
                    if hasattr(response, 'usage_metadata'):
                        usage_metadata = response.usage_metadata

                    message_data = {"role": "assistant", "content": full_response}
                    
                    # 이미지가 있는 경우에만 키 추가
                    if response_image:
                        message_data["image"] = response_image
                    
                    st.session_state.messages.append(message_data)

                    # 토큰 사용량 표시 (LLM을 썼을 때만)
                    if usage_metadata:
                        input_tokens = usage_metadata.prompt_token_count
                        output_tokens = usage_metadata.candidates_token_count
                        total_tokens = usage_metadata.total_token_count
                        st.caption(f"💰 토큰 사용량: {total_tokens} (In: {input_tokens} / Out: {output_tokens})")

                    # # response 객체 안에 usage_metadata가 들어있습니다.
                    # if response.usage_metadata:
                    #     input_tokens = response.usage_metadata.prompt_token_count
                    #     output_tokens = response.usage_metadata.candidates_token_count
                    #     total_tokens = response.usage_metadata.total_token_count
                        
                    #     # 화면에 작게 표시 (st.caption 사용)
                    #     # st.caption(f"💰 토큰 사용량: {response.usage_metadata.total_token_count}")
                    #     st.caption(f"💰 토큰 사용량: 입력 {input_tokens} + 출력 {output_tokens} = 합계 {total_tokens}")
                        
                    #     # (선택사항) 터미널에도 출력해서 기록 남기기
                    #     print(f"Update: Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}")

                    #     # 응답 저장
                    #     st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                    # raise ResourceExhausted # 429에러 예외처리 테스트

                # 429 에러(ResourceExhausted) 전용 처리
                except ResourceExhausted:
                    error_msg = (
                        "하아... 너무 격렬해요... 우리 잠시만 쉬었다가 해요..."
                    )
                    response_placeholder.markdown(error_msg)
                    # 에러 메시지는 대화 기록(history)에 저장하지 않음 (선택 사항)
                
                # 그 외 일반적인 에러 처리
                except Exception as e:
                    error_msg = f"어머, 예상치 못한 문제가 발생했군요. 카페 마스터에게 이 내용을 전달해 주시겠어요?({str(e)})"
                    response_placeholder.error(error_msg)
                    if st.button("대화 다시 시작하기"):
                        st.session_state.clear()
                        st.rerun()

