import os
from dotenv import load_dotenv

load_dotenv()

GROQ_DEPRECATED_MODELS = {
    "llama3-8b-8192",
    "llama3-70b-8192",
    "llama-3.2-1b-preview",
    "llama-3.2-3b-preview",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-text-preview",
    "llama-3.2-90b-text-preview",
    "gemma-7b-it",
    "llama-guard-3-8b"
}

PROVIDER_CONFIGS = {
    "cerebras": {
        "name": "Cerebras (세레브라스 - 초당 2,000+ 토큰 세계 최고속)",
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
        "models": [
            {"id": "llama-3.3-70b", "name": "Llama 3.3 70B (추천, 극초고속 플래그십)"},
            {"id": "llama3.1-70b", "name": "Llama 3.1 70B (초고속 고성능)"},
            {"id": "llama3.1-8b", "name": "Llama 3.1 8B (초경량 순간 응답)"}
        ],
        "env_var": "CEREBRAS_API_KEY",
        "key_url": "https://cloud.cerebras.ai/"
    },
    "groq": {
        "name": "Groq (초고속 / 무료 티어 지원)",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.1-8b-instant",
        "models": [
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant (공식 표준 권장 / 초고속)"},
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile (최신 대형 플래그십)"},
            {"id": "llama-3.1-70b-versatile", "name": "Llama 3.1 70B Versatile (고성능)"},
            {"id": "deepseek-r1-distill-llama-70b", "name": "DeepSeek R1 Distill Llama 70B (수능 킬러/심층 추론)"},
            {"id": "qwen-2.5-32b", "name": "Qwen 2.5 32B (고성능 다국어)"},
            {"id": "gemma2-9b-it", "name": "Google Gemma 2 9B IT"}
        ],
        "env_var": "GROQ_API_KEY",
        "key_url": "https://console.groq.com/keys"
    },
    "deepseek": {
        "name": "DeepSeek (딥시크 - 수능 고난도 추론)",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek V3 (지문 정밀 분석 & 수능 표준 출제)"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1 (수능 킬러문항 심층 추론)"}
        ],
        "env_var": "DEEPSEEK_API_KEY",
        "key_url": "https://platform.deepseek.com/api_keys"
    },
    "solar": {
        "name": "Upstage Solar (업스테이지 솔라 - 한국어 특화)",
        "base_url": "https://api.upstage.ai/v1/solar",
        "default_model": "solar-pro",
        "models": [
            {"id": "solar-pro", "name": "Solar Pro (한국어 수능/모의고사 어휘 최적화)"},
            {"id": "solar-mini", "name": "Solar Mini (경량 고속)"}
        ],
        "env_var": "SOLAR_API_KEY",
        "key_url": "https://console.upstage.ai/api-keys"
    },
    "openai": {
        "name": "OpenAI (ChatGPT)",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini (안정적 & 가성비)"},
            {"id": "gpt-4o", "name": "GPT-4o (최고 품질)"}
        ],
        "env_var": "OPENAI_API_KEY",
        "key_url": "https://platform.openai.com/api-keys"
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "",
        "default_model": "gemini-2.0-flash",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (빠름)"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash (안정)"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro (심화)"}
        ],
        "env_var": "GEMINI_API_KEY",
        "key_url": "https://aistudio.google.com/app/apikey"
    }
}

DEFAULT_PROVIDER = "cerebras"

def get_api_key(provider: str, custom_key: str = None) -> str:
    if custom_key and custom_key.strip():
        return custom_key.strip()
    config = PROVIDER_CONFIGS.get(provider, {})
    env_var = config.get("env_var", "")
    return os.environ.get(env_var, "") or os.environ.get("GEMINI_API_KEY", "") or ""
