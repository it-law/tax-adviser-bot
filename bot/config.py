import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")

    # OpenRouter
    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Exa.ai
    EXA_API_KEY: str | None = os.getenv("EXA_API_KEY")

    # ✅ ИСПРАВЛЕНИЕ: Gemini 2.5 Flash Lite Preview теперь по умолчанию
    # Это дешевая и быстрая модель, которая не должна давать частые 429
    MODEL_NAME: str = os.getenv("MODEL_NAME", "google/gemini-2.5-flash-lite-preview-09-2025")

    # Пути к файлам законов
    DATA_DIR: str = "data"
    LAW_FILES: dict[str, str] = {
        "tax": "tax_code.txt",
        "koap": "koap_rf.txt",
        "ved": "ved_laws.txt",
    }

    # Настройки бота
    MAX_HISTORY_PAIRS: int = 2
    EXA_NUM_RESULTS: int = 3

# ВАЖНО: именно этот объект мы импортируем в main.py и других модулях
config = Config()
