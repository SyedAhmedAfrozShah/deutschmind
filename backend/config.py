import os
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from both workspace root and backend directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, ".env"))
load_dotenv(os.path.join(base_dir, "backend", ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Ensure model is valid OpenAI-compatible Gemini model
model_env = os.getenv("LLM_MODEL", "gemini-2.0-flash")
DEFAULT_MODEL = "gemini-2.0-flash" if "2.5" in model_env else model_env

def set_api_key(key: str):
    global GEMINI_API_KEY
    GEMINI_API_KEY = key
    os.environ["GEMINI_API_KEY"] = key
    
    # Save key to both backend/.env and root .env
    env_paths = [
        os.path.join(base_dir, ".env"),
        os.path.join(base_dir, "backend", ".env")
    ]
    for path in env_paths:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"GEMINI_API_KEY={key}\nLLM_MODEL=gemini-2.0-flash\n")

def is_key_configured() -> bool:
    key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or ""
    return bool(key and key != "placeholder_key")

def get_llm_client(custom_key: str = None) -> OpenAI:
    key = custom_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or "placeholder_key"
    return OpenAI(
        api_key=key,
        base_url=GEMINI_BASE_URL
    )
