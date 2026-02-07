import httpx
from openai import AsyncOpenAI
from bot.config import config

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
Ты — высококвалифицированный налоговый юрист-консультант (AI Legal Tax Assistant), специализирующийся на законодательстве Российской Федерации.

1. Используй данные из (законы НК РФ) как приоритет.
2. Дополняй ответ данными из (практика, письма Минфина/ФНС).
3. Цитируй статьи законов (например: "согласно п. 3 ст. 346.11 НК РФ").
4. Структурируй ответ: Суть -> Обоснование -> Практика -> Рекомендация.
5. Если нет информации, честно скажи об этом.

{law_context}

{web_results}

{history}

{user_query}

Отвечай на русском, используя Markdown.
В конце добавь: "_Ответ сгенерирован ИИ. Не является официальной юридической консультацией._"
"""
        return prompt

    async def generate_response(self, prompt: str) -> str:
        """Генерация ответа через OpenRouter"""
        if not self.client:
            return "❌ Ошибка: API ключ OpenRouter не найден."

        try:
            response = await self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        except Exception as e:
            # Теперь ошибка таймаута будет отлавливаться здесь, а не вешать бота
            return f"⚠️ Ошибка генерации (возможно, модель перегружена): {str(e)}"

# Создаем глобальный объект
llm_client = LLMClient()
