import os
import asyncio
import random
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest

from bot.config import config
from bot.router import detect_topic
from bot.search import exa_search
from bot.llm import llm_client
from bot.storage import conversation_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

SEARCH_STATUSES = [
    "🔍 Изучаю законодательную базу...",
    "🌐 Проверяю актуальную судебную практику...",
    "⚖️ Сверяюсь с последними изменениями в законах...",
    "📂 Поднимаю архивы документов...",
]

GENERATING_STATUSES = [
    "📝 Формулирую юридическое заключение...",
    "🤖 Анализирую найденные факты...",
    "💡 Готовлю рекомендации для вас...",
    "✍️ Пишу ответ...",
]

@router.message(CommandStart())
async def cmd_start(message: Message):
    conversation_storage.clear_history(message.from_user.id)
    await message.answer(
        "👋 **Здравствуйте!**\n\n"
        "Я — ваш AI-помощник по российскому праву. Помогаю разобраться в налогах, штрафах и документах.\n\n"
        "🏛 **Что я умею:**\n"
        "• Найти статью НК РФ или КоАП\n"
        "• Объяснить сложные законы простым языком\n"
        "• Подобрать судебную практику\n\n"
        "Напишите ваш вопрос, и я начну поиск! 👇",
        parse_mode=None
    )

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    conversation_storage.clear_history(message.from_user.id)
    await message.answer("🧹 Контекст диалога очищен.", parse_mode=None)

@router.message(F.text)
async def handle_question(message: Message):
    if message.text.startswith("/"):
        return

    user_id = message.from_user.id
    user_query = message.text

    status_msg = await message.answer("⏳ Принял вопрос, начинаю анализ...", parse_mode=None)

    async def update_status(text):
        try:
            await status_msg.edit_text(f"⏳ {text}", parse_mode=None)
        except Exception:
            pass

    try:
        topic = detect_topic(user_query)
        
        law_file = config.LAW_FILES.get(topic, config.LAW_FILES["tax"])
        law_path = os.path.join(config.DATA_DIR, law_file)
        law_context = ""
        
        try:
            if os.path.exists(law_path):
                with open(law_path, "r", encoding="utf-8") as f:
                    law_context = f.read()[:50000]
        except Exception as e:
            logger.error(f"Error reading law file: {e}")

        await update_status(random.choice(SEARCH_STATUSES))
        try:
            web_results = await asyncio.wait_for(
                exa_search.search(user_query, num_results=config.EXA_NUM_RESULTS),
                timeout=25.0
            )
        except asyncio.TimeoutError:
            web_results = "Поиск занял слишком много времени."
        except Exception as e:
            logger.error(f"Search error: {e}")
            web_results = "Ошибка поиска."

        await update_status(random.choice(GENERATING_STATUSES))
        
        history = conversation_storage.get_formatted_history(user_id)
        prompt = llm_client.build_prompt(
            user_query=user_query,
            law_context=law_context,
            web_results=web_results,
            history=history,
        )

        try:
            answer = await asyncio.wait_for(
                llm_client.generate_response(prompt),
                timeout=90.0
            )
        except asyncio.TimeoutError:
            answer = "⚠️ Модель не успела ответить вовремя. Попробуйте упростить вопрос."
        
        conversation_storage.add_message(user_id, "user", user_query)
        conversation_storage.add_message(user_id, "assistant", answer)

        try:
            await status_msg.delete()
        except Exception:
            pass

        await message.answer(answer, parse_mode=None)

    except Exception as e:
        logger.error(f"Global handler error: {e}")
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.", parse_mode=None)
