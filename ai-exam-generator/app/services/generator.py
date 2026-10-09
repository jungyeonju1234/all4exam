import os
import json
import re
from typing import Dict, Any, List, Optional
from app.config import PROVIDER_CONFIGS, DEFAULT_PROVIDER, get_api_key

# Gemini SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

# OpenAI SDK (works for Cerebras, Groq, DeepSeek, Upstage Solar, OpenAI)
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def clean_json_response(text: str) -> str:
    """
    1. <think>...</think> 및 추론 태그 제거
    2. 마크다운 ```json ... ``` 추출
    3. 가장 바깥쪽 { ... } 또는 [ ... ] 탐색 추출
    """
    if not text:
        return "{}"
        
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.DOTALL).strip()
    
    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_match:
        text = code_match.group(1).strip()
        
    first_brace = text.find("{")
    first_bracket = text.find("[")
    
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        last_brace = text.rfind("}")
        if last_brace != -1:
            return text[first_brace:last_brace+1]
    elif first_bracket != -1:
        last_bracket = text.rfind("]")
        if last_bracket != -1:
            return text[first_bracket:last_bracket+1]
            
    return text.strip()


def call_llm(
    prompt: str,
    provider: str = "cerebras",
    model: Optional[str] = None,
    custom_api_key: Optional[str] = None,
    json_mode: bool = True
) -> str:
    """
    지정된 AI 제공자(Cerebras, Groq, DeepSeek, Upstage Solar, OpenAI, Gemini)로 프롬프트를 전송하고 텍스트 응답을 반환합니다.
    """
    provider = provider.lower() if provider else DEFAULT_PROVIDER
    if provider not in PROVIDER_CONFIGS:
        provider = DEFAULT_PROVIDER

    conf = PROVIDER_CONFIGS[provider]
    api_key = get_api_key(provider, custom_api_key)
    
    if not api_key:
        raise ValueError(f"{conf['name']}의 API 키가 입력되지 않았습니다. 우측 상단 설정에서 API 키를 입력해주세요.")

    # 1. Gemini
    if provider == "gemini":
        if not genai:
            raise ImportError("google-genai 라이브러리가 필요합니다.")
        client = genai.Client(api_key=api_key)
        
        target_model = model or conf["default_model"]
        candidate_models = [target_model, "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        for m in candidate_models:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json" if json_mode else "text/plain",
                        temperature=0.3
                    )
                )
                return resp.text
            except Exception as e:
                err_str = str(e)
                if ("404" in err_str or "NOT_FOUND" in err_str or "is no longer available" in err_str) and m != candidate_models[-1]:
                    continue
                raise e

    # 2. OpenAI-compatible Providers (Cerebras, Groq, DeepSeek, Upstage Solar, OpenAI)
    if not OpenAI:
        raise ImportError("openai 라이브러리가 필요합니다.")

    base_url = conf.get("base_url")
    client_args = {"api_key": api_key}
    if base_url:
        client_args["base_url"] = base_url

    client = OpenAI(**client_args)

    candidate_models = []
    if model and model.strip():
        candidate_models.append(model.strip())
    
    for m_obj in conf.get("models", []):
        m_id = m_obj["id"]
        if m_id not in candidate_models:
            candidate_models.append(m_id)
            
    if provider == "groq":
        extra_groq = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "llama-3.1-70b-versatile"]
        for eg in extra_groq:
            if eg not in candidate_models:
                candidate_models.append(eg)
    elif provider == "cerebras":
        extra_cerebras = ["llama-3.3-70b", "llama3.1-70b", "llama3.1-8b"]
        for ec in extra_cerebras:
            if ec not in candidate_models:
                candidate_models.append(ec)

    last_error = None
    for target_model in candidate_models:
        messages = [
            {"role": "system", "content": "You are a master Korean CSAT (수능) item writer. You craft intellectually rigorous, multi-step deductive reasoning exam questions with extremely sophisticated distractors."},
            {"role": "user", "content": prompt}
        ]

        create_kwargs = {
            "model": target_model,
            "messages": messages,
            "temperature": 0.4
        }

        if json_mode and provider != "cerebras" and "reasoner" not in target_model.lower():
            create_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = client.chat.completions.create(**create_kwargs)
            content = response.choices[0].message.content
            if content and content.strip():
                return content
        except Exception as e:
            err_str = str(e)
            last_error = e
            if "response_format" in err_str:
                try:
                    del create_kwargs["response_format"]
                    response = client.chat.completions.create(**create_kwargs)
                    return response.choices[0].message.content
                except Exception as inner_e:
                    err_str = str(inner_e)
                    last_error = inner_e
            
            if "model_not_found" in err_str or "does not exist" in err_str or "404" in err_str or "not found" in err_str:
                continue
            else:
                raise e

    raise last_error or RuntimeError("AI API 호출에 실패했습니다.")


def analyze_document_content(
    text_content: str, 
    provider: str = "cerebras",
    model: Optional[str] = None,
    custom_api_key: Optional[str] = None
) -> Dict[str, Any]:
    prompt = f"""
당신은 대한민국 고등학교 교육과정 및 수능/모의고사 출제 전문가입니다.
제공된 학습 자료의 핵심을 정밀 분석하여 다음 3가지를 JSON 형식으로 추출해주세요.

[분석 요구사항]
1. summary (핵심 요약): 지문의 핵심 주장, 전제, 주요 논점, 인과 메커니즘을 3~5개 글머리기호의 수준 높은 학술적 문장으로 요약하세요.
2. passage (정리된 본문 지문): 문제 출제의 바탕이 될 순수 지문 텍스트입니다.
3. detected_style (감지된 문제 양식): 문서 내 기존 문제 형식이 있다면 기술하고, 없으면 수능 표준형으로 설정하세요.

[입력 텍스트]
{text_content[:15000]}

반드시 아래 JSON 규격으로만 응답하세요:
{{
  "summary": "• 핵심 요약 1\\n• 핵심 요약 2\\n• 핵심 요약 3",
  "passage": "정리된 지문 본문 내용...",
  "detected_style": {{
    "has_question_style": false,
    "template_name": "수능 종합 모의고사형 (다양한 유형 복합)",
    "description": "일치/불일치, 보기 적용, 빈칸 추론, 비판적 평가 복합 구성",
    "sample_format": "수능 표준 양식"
  }}
}}
"""
    raw_text = call_llm(
        prompt=prompt,
        provider=provider,
        model=model,
        custom_api_key=custom_api_key,
        json_mode=True
    )
    cleaned = clean_json_response(raw_text)
    return json.loads(cleaned)


def get_subject_prompt_context(subject: str = "korean") -> Dict[str, Any]:
    """
    대한민국 대학수학능력시험 국어 영역(독서·문학) 전문 출제 지침 및 발문/유형 템플릿 반환
    """
    return {
        "name": "국어 영역 (독서 / 문학)",
        "role": "대한민국 대학수학능력시험 국어영역 수석 출제위원장",
        "type_guide": """
- **문항 1 [지문 심층 구조 및 전제 분석]**: 글의 전개 방식, 필자의 숨겨진 전제(Implicit Premise), 핵심 논점 간의 인과관계
- **문항 2 [<보기> 새로운 학설/가상 사례 심층 적용]**: 지문의 핵심 원리를 새로운 상황, 판례, 과학 실험, 예술 비평에 적용
- **문항 3 [문맥적 의미 및 빈칸/어휘 심층 추론]**: ㉠과 ㉡의 관계, 빈칸 (A)에 들어갈 논리적 귀결, 함축적 의미 파악
- **문항 4 [비판적 평가 및 반론 제기]**: 윗글의 주장에 대한 논리적 반박, 한계점 지적, 타당성 검증
- **문항 5 이상 [조건부 추론 및 종합 평가]**: 복합 조건 하에서의 결과 예측 및 다각도 비판
""",
        "box_guide": "[보기]에 새로운 가상 상황, 반대 학설, 데이터 또는 구체적 사례를 적극 구성하세요."
    }


def generate_exam_questions(
    passage: str,
    question_style: str,
    difficulty: str = "수능 킬러 (1등급 변별)",
    question_count: int = 3,
    subject: str = "korean",
    provider: str = "cerebras",
    model: Optional[str] = None,
    custom_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    국어, 한국지리, 윤리 등 과목별 수능 킬러 원칙을 적용하고, 
    대량 문항 요청(예: 1~15문항)도 안정적으로 분할/완성하여 반환합니다.
    """
    subj_info = get_subject_prompt_context(subject)
    
    difficulty_instructions = {
        "고2 기본": """
- 전국연합학력평가 고2 수준
- 단순 텍스트 일치 확인이 아니라 문맥적 의미 파악, 문단 간 논리적 연결성, 개념의 적용을 측정해야 합니다.
""",
        "고3 심화": """
- 평가원 모의평가 고3 수준
- 지문 내 여러 문단에 흩어진 정보들을 종합적으로 결합해야만 풀 수 있는 2단계 추론 문항.
- 완벽한 패러프레이징(재진술) 및 매력적인 함정 선지 배치.
""",
        "수능 킬러 (1등급 변별)": """
- **수능 1등급 컷을 가르는 초고난도 킬러 문항 (정답률 20~35%대)**
- 지문의 표면적 서술을 넘어, 필자의 '숨겨진 전제(Implicit Premise)'나 '논리적 한계'를 묻는 문항.
- 5개 선지 모두 학술적이고 매력적으로 작성하되, 단 1개의 선지만이 지문의 미세한 논리적 정합성을 충족해야 함.
""",
        "극악 킬러 (만점 방지용)": """
- **수능 전 과목 역사상 최고난도 킬러 문항 (정답률 10~20%대 만점 방지용)**
- 지문의 이론 체계를 완전히 체화한 상태에서만 풀 수 있는 3~4단계 다층 연역 추론 문항.
- 필수 요구사항:
  1. 지문 단어의 단순 치환 절대 금지.
  2. 오답 선지들은 대충 만든 것이 아니라 '인과관계의 미세한 전도', '외연과 내포의 교묘한 왜곡', '충분조건을 필요조건으로 착각하게 하는 정교한 논리 함정'을 가질 것.
  3. 모든 문항에 현실적이고 깊이 있는 학술적 <보기> 시나리오나 반박 가설을 적극 포함할 것.
"""
    }
    
    diff_desc = difficulty_instructions.get(difficulty, difficulty_instructions["수능 킬러 (1등급 변별)"])
    
    # 문항 수가 6개 이하인 경우 단일 호출, 7개 이상인 경우 안정적 배치(Batch) 호출
    target_count = max(1, min(20, question_count))
    
    def _generate_chunk(start_num: int, count: int, prior_context: str = "") -> List[Dict[str, Any]]:
        prompt = f"""
당신은 {subj_info['role']}입니다.
출제 대상 영역: **{subj_info['name']}**
제시된 [지문]을 바탕으로 **{start_num}번부터 {start_num + count - 1}번까지 총 {count}문항**의 최고난도 수능 문제를 출제하세요.

[⚠️ 과목별 출제 지침: {subj_info['name']}]
{subj_info['type_guide']}
{subj_info['box_guide']}

[⚠️ 목표 난이도: {difficulty}]
{diff_desc}

{f"[이전 문항 목록 (중복 출제 방지)]\\n{prior_context}\\n" if prior_context else ""}

[지문 본문]
{passage}

반드시 다른 부가 설명 없이 다음 JSON 객체 형식(키: "questions")으로만 출력하세요.
문항 번호는 반드시 **{start_num}**번부터 순서대로 매기세요:
{{
  "questions": [
    {{
      "number": {start_num},
      "type": "multiple_choice",
      "question": "{start_num}번 문제 발문",
      "box_content": "[보기]\\n... (필요 없을 경우 빈 문자열)",
      "options": [
        "① 정밀하게 설계된 고난도 선지 1",
        "② 정밀하게 설계된 고난도 선지 2",
        "③ 정밀하게 설계된 고난도 선지 3",
        "④ 정밀하게 설계된 고난도 선지 4",
        "⑤ 정밀하게 설계된 고난도 선지 5"
      ],
      "correct_answer": "③",
      "explanation": "정답이 정답인 엄밀한 논리적 근거 및 오답 선지별 상세 분석",
      "source_evidence": "지문 내 결정적 단서 문장 및 출제 근거",
      "difficulty_label": "{difficulty}"
    }}
  ]
}}
"""
        raw_text = call_llm(
            prompt=prompt,
            provider=provider,
            model=model,
            custom_api_key=custom_api_key,
            json_mode=True
        )
        cleaned = clean_json_response(raw_text)
        data = json.loads(cleaned)
        
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "questions" in data and isinstance(data["questions"], list):
                items = data["questions"]
            elif "question" in data:
                items = [data]
            else:
                for v in data.values():
                    if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                        items = v
                        break
                if not items:
                    items = [data]
                    
        # 번호 재보정
        for idx, itm in enumerate(items):
            if isinstance(itm, dict):
                itm["number"] = start_num + idx
                itm["difficulty_label"] = difficulty
        return items

    if target_count <= 6:
        return _generate_chunk(1, target_count)
    else:
        # 분할 생성 (예: 10개면 5개 + 5개, 15개면 5개 + 5개 + 5개)
        all_questions = []
        current_num = 1
        remaining = target_count
        
        while remaining > 0:
            batch_size = min(5, remaining)
            prior = "\n".join([f"문제 {q['number']}: {q['question']}" for q in all_questions])
            chunk = _generate_chunk(current_num, batch_size, prior_context=prior)
            all_questions.extend(chunk)
            current_num += len(chunk)
            remaining -= len(chunk)
            if len(chunk) == 0:
                break
                
        return all_questions


def regenerate_single_question(
    passage: str,
    question_style: str,
    difficulty: str,
    existing_questions: List[Dict[str, Any]],
    target_number: int,
    subject: str = "korean",
    provider: str = "cerebras",
    model: Optional[str] = None,
    custom_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    특정 번호의 문항 1개만 해당 과목(국어, 한국지리, 윤리 등)의 고난도 유형으로 새롭게 재생성합니다.
    """
    subj_info = get_subject_prompt_context(subject)
    
    other_questions_summary = []
    for q in existing_questions:
        if q.get("number") != target_number:
            other_questions_summary.append(f"문제 {q.get('number')}: {q.get('question')}")
            
    other_context = "\n".join(other_questions_summary) if other_questions_summary else "없음"

    prompt = f"""
당신은 {subj_info['role']}입니다.
출제 대상 영역: **{subj_info['name']}**
현재 시험지에서 **{target_number}번 문항**을 완전히 새로운 고난도 심층 추론 문항으로 교체 출제해야 합니다.

[기존 다른 문항들 (중복 출제 방지)]
{other_context}

[⚠️ 과목별 출제 지침: {subj_info['name']}]
{subj_info['type_guide']}
{subj_info['box_guide']}

[출제 요구사항]
1. 목표 난이도: **{difficulty}** (단순 일치/불일치가 아닌, 다단계 추론이나 <보기> 자료/사상가 비교/통계 분석형으로 출제)
2. 기존 다른 문제들과 측정하는 영역 및 발문 형식이 겹치지 않는 신선한 문항을 만드세요.
3. 각 오답 선지는 인과관계 전도나 전제 비약 등 매력적인 함정을 갖추어야 합니다.
4. 문항 번호는 반드시 **{target_number}** 로 지정하세요.

[지문 본문]
{passage}

반드시 다른 텍스트 없이 다음 단일 JSON 객체 형식으로만 응답하세요:
{{
  "number": {target_number},
  "type": "multiple_choice",
  "question": "새로운 고난도 문제 발문",
  "box_content": "[보기]\\n... (필요 없을 경우 빈 문자열)",
  "options": [
    "① 선지 1",
    "② 선지 2",
    "③ 선지 3",
    "④ 선지 4",
    "⑤ 선지 5"
  ],
  "correct_answer": "정답",
  "explanation": "상세 해설 (오답 선지별 오류 이유 포함)",
  "source_evidence": "지문 내 근거 문장",
  "difficulty_label": "{difficulty}"
}}
"""
    raw_text = call_llm(
        prompt=prompt,
        provider=provider,
        model=model,
        custom_api_key=custom_api_key,
        json_mode=True
    )
    cleaned = clean_json_response(raw_text)
    data = json.loads(cleaned)
    if isinstance(data, dict):
        if "question" in data and isinstance(data["question"], dict):
            return data["question"]
        return data
    elif isinstance(data, list) and len(data) > 0:
        return data[0]
    return data
