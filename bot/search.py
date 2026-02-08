import asyncio
import logging
from typing import Any

import aiohttp

from bot.config import config

logger = logging.getLogger(__name__)


class TavilySearch:
    def __init__(self):
        self.api_key = config.TAVILY_API_KEY
        self.base_url = "https://api.tavily.com/search"

    async def search(self, query: str) -> str:
        """Поиск актуальной информации через Tavily."""
        if not self.api_key:
            return ""

        payload: dict[str, Any] = {
            "query": query,
            "search_depth": config.TAVILY_SEARCH_DEPTH,
            "max_results": config.TAVILY_MAX_RESULTS,
            "include_domains": config.TAVILY_INCLUDE_DOMAINS,
            "topic": "general",
            "country": "russia",
            "include_answer": False,
            "include_raw_content": False,
        }

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
                        logger.error(f"Tavily error: {resp.status} {text}")
                        return ""
                    data = await resp.json()
        except asyncio.TimeoutError:
            logger.error("Tavily request timed out")
            return ""
        except Exception as e:
            logger.error(f"Tavily request error: {e}")
            return ""

        results = data.get("results") or []
        if not results:
            return ""

        formatted = []
        for idx, item in enumerate(results, 1):
            title = (item.get("title") or "").strip()
            url = (item.get("url") or "").strip()
            content = (item.get("content") or item.get("snippet") or "").strip()
            if content:
                content = content[:1500]
            formatted.append(
                f"Источник {idx}: {title}\nURL: {url}\nСниппет: {content}"
            )

        return "\n\n".join(formatted)


tavily_search = TavilySearch()


async def get_tavily_search(query: str) -> str:
    return await tavily_search.search(query)
