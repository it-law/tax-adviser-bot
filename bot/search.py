import asyncio
from exa_py import Exa
from bot.config import config

class ExaSearch:
    def __init__(self):
        # Инициализируем клиента только если есть ключ
        if config.EXA_API_KEY:
            self.client = Exa(api_key=config.EXA_API_KEY)
        else:
            self.client = None

    async def search(self, query: str, num_results: int = 3) -> str:
        """Поиск актуальной информации через Exa.ai"""
        if not self.client:
            return "⚠️ API ключ Exa не найден. Поиск отключен."

        # Внутренняя функция для запуска в отдельном потоке
        def _do_request():
            enhanced_query = f"{query} Российская Федерация законодательство"
            return self.client.search_and_contents(
                enhanced_query,
                num_results=num_results,
                use_autoprompt=True,
                text={"max_characters": 2000},
                category="news",
            )

        try:
            # ✅ ИСПРАВЛЕНИЕ: Запускаем синхронный поиск в асинхронном режиме
            # Это предотвращает блокировку бота во время поиска
            response = await asyncio.to_thread(_do_request)

            formatted_results = []
            if response and response.results:
                for result in response.results:
                    formatted_results.append(
                        f"Источник: {result.title}\n"
                        f"URL: {result.url}\n"
                        f"Текст: {result.text[:1500]}...\n"
                    )
            else:
                return "Ничего не найдено."

            return "\n\n".join(formatted_results)
        except Exception as e:
            return f"Ошибка поиска: {str(e)}"

# Создаем глобальный объект
exa_search = ExaSearch()
