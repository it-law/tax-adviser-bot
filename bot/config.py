import os
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")

    # OpenRouter
    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Tavily
    TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")
    TAVILY_MAX_RESULTS: int = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
    TAVILY_SEARCH_DEPTH: str = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
    TAVILY_COUNTRY: str = os.getenv("TAVILY_COUNTRY", "Poland")
    TAVILY_INCLUDE_DOMAINS: list[str] = [
        "pravo.gov.ru",
        "consultant.ru",
        "nalog.gov.ru",
        "garant.ru",
        "minfin.gov.ru",
        "cbr.ru",
        "klerk.ru",
        "buh.ru",
        "nalog-nalog.ru",
        "advgazeta.ru",
        "pravovest-audit.ru",
    ]

    # Основная модель
    MODEL_NAME: str = os.getenv("MODEL_NAME", "google/gemini-2.0-flash-001")
    # Запасные модели (если основная недоступна)
    MODEL_FALLBACK: str | None = os.getenv("MODEL_FALLBACK")
    _fallbacks_raw: str = os.getenv("MODEL_FALLBACKS", "")
    MODEL_FALLBACKS: list[str] = [m.strip() for m in _fallbacks_raw.split(",") if m.strip()]
    if MODEL_FALLBACK:
        MODEL_FALLBACKS = [MODEL_FALLBACK] + MODEL_FALLBACKS

    # Пути к файлам законов
    DATA_DIR: str = "data"
    LAW_FILES: dict[str, str] = {
        "tax": "tax_code.txt",
        "koap": "koap_rf.txt",
        "ved": "ved_laws.txt",
    }

    # Настройки бота
    MAX_HISTORY_PAIRS: int = 2

# ВАЖНО: именно этот объект мы импортируем в main.py и других модулях
config = Config()
