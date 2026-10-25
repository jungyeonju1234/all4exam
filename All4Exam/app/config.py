import os
from dotenv import load_dotenv

load_dotenv()

PROVIDER_CONFIGS = {
    "cerebras": {
        "name": "Cerebras AI",
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "gpt-oss-120b",
        "models": [
            {"id": "gpt-oss-120b", "name": "GPT OSS 120B (추천, 초고속 플래그십)"},
            {"id": "qwen-3.8-27b", "name": "Qwen 3.8 27B (경량 고속)"}
        ],
        "env_var": "CEREBRAS_API_KEY",
        "key_url": "https://cloud.cerebras.ai/"
    }
}

DEFAULT_PROVIDER = "cerebras"

def get_api_key(provider: str, custom_key: str = None) -> str:
    if custom_key and custom_key.strip():
        return custom_key.strip()
    config = PROVIDER_CONFIGS.get(provider, {})
    env_var = config.get("env_var", "")
    return os.environ.get(env_var, "") or ""
