import os

from dotenv import load_dotenv

load_dotenv()

MODEL_NAME: str = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4-5")
PROVIDER: str = MODEL_NAME.split("/")[0] if "/" in MODEL_NAME else "anthropic"
