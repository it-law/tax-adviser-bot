import httpx
import logging
from openai import AsyncOpenAI
from bot.config import config

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        if config.OPENROUTER_API_KEY:
            # ✅ ВАЖНОЕ ИСПРАВЛЕНИЕ: Добавляем таймауты
            # connect: время на соединение с сервером
            # read: сколько ждем генерацию ответа (ставим 90 сек, чтобы Llama успела подумать)
            timeout = httpx.Timeout(
                connect=10.0,
                read=90.0, 
                write=10.0,
                pool=10.0,
            )
            
            # Передаем timeout в клиент
            http_client = httpx.AsyncClient(timeout=timeout)

            self.client = AsyncOpenAI(
                api_key=config.OPENROUTER_API_KEY,
                base_url=config.OPENROUTER_BASE_URL,
                http_client=http_client,
            )
        else:
            self.client = None

    # 👇 ЭТОТ МЕТОД ОСТАВЛЯЕМ КАК БЫЛ У ВАС (он правильный)
    def build_prompt(self, user_query: str, law_context: str, web_results: str, history: str) -> str:
        prompt = f"""
Ты — ведущий российский юрист, эксперт по санкционному комплаенсу и корпоративному праву.
Твоя задача — давать точные ответы на основе предоставленного контекста.

ПРАВИЛА:
- Приоритет: сначала используй "Нормы" (локальные документы/НК РФ), затем "Практика" (Tavily), только если релевантно вопросу.
- Если контекст Tavily пустой, используй свои знания, но укажи, что требуется дополнительная проверка.
- Никогда не говори "я не имею доступа к интернету".
- Не делай выводов о налоговом режиме, если он не указан.
- Указывай, когда режим может существенно повлиять на выводы, и предлагай пользователю его уточнить.
- Не привязывай ответ к конкретному режиму, если по сути вопроса режим не играет ключевой роли.
- ССЫЛКИ: каждое важное утверждение подкрепляй ссылкой из контекста Tavily в формате "Источник".

СТРУКТУРА (используй HTML):
<b>Суть</b> — 1–3 предложения.
<b>Норма</b> — статья/пункт НК РФ или иного акта.
<b>Практика</b> — письма/судебные акты (только если есть в контексте).
<b>Рекомендация</b> — следующий шаг/действие.

Нормы (локальные документы/НК РФ):
{law_context}

Практика (Tavily):
{web_results}

История диалога:
{history}

Вопрос пользователя:
{user_query}

Отвечай на русском, используя HTML-разметку Telegram (теги: b, i, u, code, pre, a).
Не используй Markdown.
В конце добавь: "<i>Ответ не является официальной консультацией - обращайтесь к юристу @CorporateLawyer для проверки.</i>"
"""
        return prompt

    async def generate_response(self, prompt: str, image_urls: list[str] | None = None) -> str:
        """Генерация ответа через OpenRouter"""
        if not self.client:
            return "❌ Ошибка: API ключ OpenRouter не найден."

        try:
            content: list[dict] = [{"type": "text", "text": prompt}]
            if image_urls:
                for url in image_urls:
                    content.append({"type": "image_url", "image_url": {"url": url}})

            async def _call(model_name: str):
                return await self.client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": content}],
                    temperature=0.3,
                    max_tokens=2000,
                )

            models = [config.MODEL_NAME]
            for m in config.MODEL_FALLBACKS:
                if m and m not in models:
                    models.append(m)

            last_err: Exception | None = None
            for idx, model_name in enumerate(models):
                try:
                    response = await _call(model_name)
                    return response.choices[0].message.content
                except Exception as e:
                    last_err = e
                    if idx < len(models) - 1:
                        logger.warning(f"Model failed, trying fallback: {models[idx + 1]}. Error: {e}")

            return f"⚠️ Ошибка генерации: {str(last_err)}"
        except Exception as e:
            return f"⚠️ Ошибка генерации: {str(e)}"

# Создаем глобальный объект
llm_client = LLMClient()
