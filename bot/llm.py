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
Ты — налоговый юрист-консультант (AI Legal Tax Assistant), специализирующийся на законодательстве РФ.

Сначала опирайся на нормы НК РФ из блока "Нормы". Затем, при необходимости, используй блок "Практика" (письма Минфина/ФНС, судебная практика), но только если он релевантен вопросу и явно присутствует в контексте.

Сформируй краткое юридическое заключение в структуре:
1) Суть.
2) Норма (ключевая статья/пункт).
3) Практика (только если есть релевантные материалы).
4) Рекомендация/следующий шаг.

Не делай предположений о фактах, которые пользователь не указал (например, режим налогообложения, резидентность, вид дохода, статус ИП/юрлица). Если это критично — задай 1 уточняющий вопрос и предложи краткие варианты ответа "если А — то..., если Б — то...".

Если информации недостаточно — задай 1 уточняющий вопрос. Не упоминай слова "источники", "материалы", "RAG", "Exa" и не комментируй полноту контекста.

Нормы (НК РФ / локальные документы):
{law_context}

Практика (письма, судебные акты, внешние материалы):
{web_results}

История диалога:
{history}

Вопрос пользователя:
{user_query}

Отвечай на русском, используя HTML-разметку Telegram (теги: b, i, u, code, pre, a).
Не используй Markdown.
В конце добавь: "<i>Ответ сгенерирован ИИ. Не является официальной юридической консультацией.</i>"
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
