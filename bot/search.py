import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp

from bot.config import config

logger = logging.getLogger(__name__)


class TavilySearch:
    def __init__(self):
        self.api_key = config.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    async def search_results(self, query: str) -> list[dict]:
        """Поиск актуальной информации через Tavily (сырые результаты)."""
        if not self.api_key:
            logger.warning("Tavily API key is missing; web search disabled.")
            return []

        logger.info(f"Tavily search triggered for: {query}")
        country = (getattr(config, "TAVILY_COUNTRY", "Russia") or "").strip()
        payload: dict[str, Any] = {
            "query": query,
            "search_depth": config.TAVILY_SEARCH_DEPTH,
            "max_results": config.TAVILY_MAX_RESULTS,
            "include_domains": config.TAVILY_INCLUDE_DOMAINS,
            "topic": "general",
            "include_answer": False,
            "include_raw_content": False,
        }
        start_date = (config.TAVILY_START_DATE or "").strip()
        end_date = (config.TAVILY_END_DATE or "").strip()
        if start_date:
            payload["start_date"] = start_date
            if end_date:
                payload["end_date"] = end_date
            else:
                payload["end_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if payload.get("start_date") or payload.get("end_date"):
            logger.info(
                "Tavily date filter: "
                f"{payload.get('start_date', '-')}"
                f"..{payload.get('end_date', '-')}"
            )
        if country:
            payload["country"] = country

        timeout = aiohttp.ClientTimeout(total=15)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.base_url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        if resp.status == 400 and "Invalid country" in text and "country" in payload:
                            logger.warning("Tavily country invalid, retrying without country filter.")
                            payload.pop("country", None)
                            async with session.post(self.base_url, json=payload, headers=headers) as resp2:
                                if resp2.status != 200:
                                    text2 = await resp2.text()
                                    logger.error(f"Tavily error: {resp2.status} {text2}")
                                    return []
                                data = await resp2.json()
                        else:
                            logger.error(f"Tavily error: {resp.status} {text}")
                            return []
                    else:
                        data = await resp.json()
        except asyncio.TimeoutError:
            logger.error("Tavily request timed out")
            return []
        except Exception as e:
            logger.error(f"Tavily request error: {e}")
            return []

        results = data.get("results") or []
        if not results:
            logger.info("Tavily search returned 0 results.")
            return []

        logger.info(f"Tavily search returned {len(results)} results.")
        return results

    async def search(self, query: str) -> str:
        """Поиск актуальной информации через Tavily."""
        results = await self.search_results(query)
        return format_results(results)


def _short_title(title: str, max_words: int = 4) -> str:
    t = " ".join(title.strip().split())
    if not t:
        return ""
    words = t.split()
    return " ".join(words[:max_words])


def _extract_date(item: dict) -> str:
    for key in ("published_date", "publishedDate", "last_updated", "lastUpdated", "date"):
        value = item.get(key)
        if value:
            return str(value).strip()
    return ""


def format_results(results: list[dict]) -> str:
    formatted: list[str] = []
    for item in results:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        content = (item.get("content") or item.get("snippet") or "").strip()
        if content:
            content = content[:1500]
        label = _short_title(title) or "Источник"
        date_value = _extract_date(item)
        date_suffix = f" ({date_value})" if date_value else ""
        if url:
            link = f"<a href=\"{url}\">{label}</a>"
        else:
            link = label
        formatted.append(f"{content}\n{link}{date_suffix}".strip())
    return "\n\n---\n\n".join(formatted) if formatted else ""


def prepare_search_query(user_query: str) -> str:
    """Улучшает поисковый запрос для более точных результатов."""
    q = user_query.lower()

    if ("продаж" in q or "реализац" in q) and ("дол" in q or "участ" in q):
        if "организац" in q or "компани" in q or "ооо" in q:
            return f"{user_query} налог на прибыль организаций статья 280 НК РФ письмо Минфина"
        return f"{user_query} НДФЛ статья 217 НК РФ"

    if "иностран" in q or "нерезидент" in q or "катар" in q:
        return f"{user_query} валютный контроль санкции ЦБ РФ"

    if "санкци" in q or "ограничен" in q or "запрет" in q:
        return f"{user_query} указ президента санкции недружественные страны"

    return user_query


tavily_search = TavilySearch()


async def web_search(query: str) -> str:
    """Поиск через Tavily для юридических запросов (с улучшенным запросом)."""
    enhanced_query = prepare_search_query(query)
    if enhanced_query != query:
        logger.info(f"Tavily search: original='{query}', enhanced='{enhanced_query}'")
    results = await tavily_search.search_results(enhanced_query)
    return format_results(results)


async def web_search_multi(user_query: str) -> str:
    """Делает несколько поисков для комплексных вопросов."""
    q = user_query.lower()
    contexts: list[str] = []

    main_context = await web_search(user_query)
    if main_context:
        contexts.append(main_context)

    if "иностран" in q or "нерезидент" in q:
        currency_query = "валютный контроль сделки с нерезидентами ЦБ РФ 2026"
        currency_context = await web_search(currency_query)
        if currency_context:
            contexts.append("--- Дополнительно: валютный контроль ---\n" + currency_context)

        sanctions_query = "санкции недружественные страны указ президента сделки 2026"
        sanctions_context = await web_search(sanctions_query)
        if sanctions_context:
            contexts.append("--- Дополнительно: санкции ---\n" + sanctions_context)

    return "\n\n===\n\n".join(contexts) if contexts else ""


async def get_tavily_search(query: str) -> str:
    return await web_search_multi(query)
