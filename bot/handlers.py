import os
import io
import base64
import asyncio
import random
import logging
import shutil
import subprocess
import tempfile
import re
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest

from bot.config import config
from bot.router import detect_topic
from bot.search import get_tavily_search
from bot.llm import llm_client
from bot.storage import conversation_storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

doc_text_by_user: dict[int, str] = {}
doc_images_by_user: dict[int, list[str]] = {}

MAX_DOC_BYTES = 200_000
MAX_DOC_CHARS = 8_000
MAX_IMAGE_ITEMS = 2
TELEGRAM_MAX_LEN = 4096

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

SEARCH_KEYWORDS = [
    "санкц",
    "ндпи",
    "изменени",
    "закон",
    "новост",
    "указ",
    "постановлен",
    "письмо",
    "практик",
    "источник",
    "ссылка",
    "фнс",
    "минфин",
]

@router.message(CommandStart())
async def cmd_start(message: Message):
    conversation_storage.clear_history(message.from_user.id)
    doc_text_by_user.pop(message.from_user.id, None)
    doc_images_by_user.pop(message.from_user.id, None)
    await message.answer(
        "Здравствуйте! Я консультант по налогам в РФ.\n\n"
        "Опишите вашу ситуацию или задайте вопрос — отвечу по сути.\n"
        "Можно прислать текст, фото, DOCX или DOC — я учту это в ответах.\n\n"
        "Примеры:\n"
        "• Налог на имущество для физлиц в моем случае\n"
        "• У меня ИП на УСН, что с НДС?\n"
        "• Что грозит за просрочку декларации?\n\n"
        "Команда: /clear — очистить контекст."
    )

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    conversation_storage.clear_history(message.from_user.id)
    doc_text_by_user.pop(message.from_user.id, None)
    doc_images_by_user.pop(message.from_user.id, None)
    await message.answer("🧹 Контекст диалога очищен.")

def _safe_trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit]

def _is_image_file(file_name: str, mime_type: str) -> bool:
    file_name = (file_name or "").lower()
    mime_type = (mime_type or "").lower()
    return mime_type.startswith("image/") or file_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"))

def _is_docx_file(file_name: str, mime_type: str) -> bool:
    file_name = (file_name or "").lower()
    mime_type = (mime_type or "").lower()
    return (
        file_name.endswith(".docx")
        or mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

def _is_doc_file(file_name: str, mime_type: str) -> bool:
    file_name = (file_name or "").lower()
    mime_type = (mime_type or "").lower()
    return file_name.endswith(".doc") or mime_type == "application/msword"

def _to_data_url(data: bytes, mime_type: str) -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"

def _read_docx_bytes(data: bytes) -> str:
    try:
        from docx import Document
    except Exception as e:
        logger.info(f"DOCX deps missing: {e}")
        return ""

    try:
        doc = Document(io.BytesIO(data))
        parts = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
        return "\n".join(parts).strip()
    except Exception as e:
        logger.error(f"DOCX parse error: {e}")
        return ""

def _read_doc_bytes(data: bytes) -> tuple[str, str | None]:
    tool = None
    if shutil.which("antiword"):
        tool = "antiword"
    elif shutil.which("catdoc"):
        tool = "catdoc"

    if not tool:
        return "", "missing_tool"

    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        if tool == "antiword":
            res = subprocess.run([tool, tmp_path], capture_output=True, text=True)
        else:
            res = subprocess.run([tool, "-w", tmp_path], capture_output=True, text=True)

        if res.returncode != 0:
            return "", "parse_error"
        return (res.stdout or "").strip(), None
    except Exception as e:
        logger.error(f"DOC parse error: {e}")
        return "", "parse_error"
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

def _store_user_image(user_id: int, data_url: str):
    images = doc_images_by_user.get(user_id, [])
    images.append(data_url)
    if len(images) > MAX_IMAGE_ITEMS:
        images = images[-MAX_IMAGE_ITEMS:]
    doc_images_by_user[user_id] = images

def _split_message(text: str, limit: int = TELEGRAM_MAX_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit + 1)
        if cut == -1:
            cut = remaining.rfind(" ", 0, limit + 1)
        if cut == -1 or cut < limit * 0.3:
            cut = limit
        parts.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts

def needs_web_search(user_query: str) -> bool:
    q = user_query.strip().lower()
    if not q:
        return False
    if len(q) > 50:
        return True
    return any(word in q for word in SEARCH_KEYWORDS)

def _extract_urls(text: str) -> list[str]:
    if not text:
        return []
    urls = re.findall(r"https?://\\S+", text)
    cleaned: list[str] = []
    seen = set()
    for url in urls:
        u = url.rstrip(").,;!?:\"'”»")
        if u not in seen:
            seen.add(u)
            cleaned.append(u)
    return cleaned

async def process_query(message: Message, user_query: str, extra_context: str = ""):
    user_id = message.from_user.id
    status_msg = await message.answer("⏳ Принял запрос, начинаю анализ...")

    async def update_status(text):
        try:
            await status_msg.edit_text(f"⏳ {text}")
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

        web_results = ""
        if needs_web_search(user_query):
            await update_status(random.choice(SEARCH_STATUSES))
            try:
                web_results = await asyncio.wait_for(
                    get_tavily_search(user_query),
                    timeout=20.0
                )
            except asyncio.TimeoutError:
                logger.error("Tavily search timeout")
                web_results = ""
            except Exception as e:
                logger.error(f"Tavily search error: {e}")
                web_results = ""

        await update_status(random.choice(GENERATING_STATUSES))
        
        history = conversation_storage.get_formatted_history(user_id)
        if extra_context:
            doc_block = f"Контекст из документа:\n{extra_context}"
            history = f"{history}\n\n{doc_block}" if history else doc_block
        elif doc_text_by_user.get(user_id):
            doc_block = f"Контекст из документа:\n{doc_text_by_user[user_id]}"
            history = f"{history}\n\n{doc_block}" if history else doc_block

        prompt = llm_client.build_prompt(
            user_query=user_query,
            law_context=law_context,
            web_results=web_results,
            history=history,
        )

        try:
            answer = await asyncio.wait_for(
                llm_client.generate_response(prompt, image_urls=doc_images_by_user.get(user_id)),
                timeout=90.0
            )
        except asyncio.TimeoutError:
            answer = "⚠️ Модель не успела ответить вовремя. Попробуйте упростить вопрос."

        urls = _extract_urls(web_results if isinstance(web_results, str) else "")
        if urls and "источники" not in answer.lower():
            sources = "<b>Источники:</b><br>" + "<br>".join(
                f"• <a href=\"{u}\">Источник {i}</a>" for i, u in enumerate(urls, 1)
            )
            answer = answer.rstrip() + "\n\n" + sources
        
        conversation_storage.add_message(user_id, "user", user_query)
        conversation_storage.add_message(user_id, "assistant", answer)

        try:
            await status_msg.delete()
        except Exception:
            pass

        for part in _split_message(answer):
            await message.answer(part)

    except Exception as e:
        logger.error(f"Global handler error: {e}")
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")

@router.message(F.photo)
async def handle_photo(message: Message):
    caption = (message.caption or "").strip()
    image_url = ""
    try:
        photo = message.photo[-1]
        buf = io.BytesIO()
        await message.bot.download(photo, destination=buf)
        buf.seek(0)
        data = buf.read()
        if len(data) <= MAX_DOC_BYTES:
            image_url = _to_data_url(data, "image/jpeg")
            _store_user_image(message.from_user.id, image_url)
    except Exception as e:
        logger.error(f"Photo download error: {e}")

    if caption:
        if image_url:
            await message.answer("Фото получил. Отвечаю по вашему вопросу.")
            await process_query(message, caption)
        else:
            await message.answer(
                "Фото получил. Файл слишком большой или не удалось прочитать. "
                "Пришлите более легкое изображение."
            )
            await process_query(message, caption)
        return

    if image_url:
        await message.answer(
            "Фото получил. Сформулируйте вопрос — отвечу с учетом изображения."
        )
    else:
        await message.answer(
            "Фото получил. Напишите, что именно нужно выяснить, и, если есть текст, перепечатайте ключевые фрагменты."
        )

@router.message(F.document)
async def handle_document(message: Message):
    doc = message.document
    caption = (message.caption or "").strip()
    file_name = (doc.file_name or "").lower()
    mime_type = (doc.mime_type or "").lower()

    text_context = ""
    image_url = ""
    if doc.file_size and doc.file_size > MAX_DOC_BYTES:
        await message.answer(
            "Документ слишком большой для обработки. Пришлите краткий фрагмент или текстовый файл."
        )
    else:
        is_text = mime_type.startswith("text/") or file_name.endswith((".txt", ".md", ".csv"))
        if is_text:
            try:
                buf = io.BytesIO()
                await message.bot.download(doc, destination=buf)
                buf.seek(0)
                text_context = buf.read().decode("utf-8", errors="ignore").strip()
                text_context = _safe_trim(text_context, MAX_DOC_CHARS)
            except Exception as e:
                logger.error(f"Document download/read error: {e}")
                text_context = ""
        elif _is_docx_file(file_name, mime_type):
            try:
                buf = io.BytesIO()
                await message.bot.download(doc, destination=buf)
                buf.seek(0)
                text_context = _read_docx_bytes(buf.read())
                text_context = _safe_trim(text_context, MAX_DOC_CHARS)
            except Exception as e:
                logger.error(f"DOCX download/read error: {e}")
                text_context = ""
        elif _is_doc_file(file_name, mime_type):
            try:
                buf = io.BytesIO()
                await message.bot.download(doc, destination=buf)
                buf.seek(0)
                text_context, doc_err = _read_doc_bytes(buf.read())
                text_context = _safe_trim(text_context, MAX_DOC_CHARS)
                if not text_context and doc_err == "missing_tool":
                    await message.answer(
                        "DOC получен, но для чтения нужен <code>antiword</code> или <code>catdoc</code>. "
                        "Установите инструмент или пришлите DOCX/текст."
                    )
            except Exception as e:
                logger.error(f"DOC download/read error: {e}")
                text_context = ""
        elif _is_image_file(file_name, mime_type):
            try:
                buf = io.BytesIO()
                await message.bot.download(doc, destination=buf)
                buf.seek(0)
                data = buf.read()
                if len(data) <= MAX_DOC_BYTES:
                    image_url = _to_data_url(data, mime_type or "image/jpeg")
                    _store_user_image(message.from_user.id, image_url)
                else:
                    text_context = ""
            except Exception as e:
                logger.error(f"Image document download error: {e}")
                text_context = ""
        else:
            await message.answer(
                "Документ получил. Сейчас читаю только текстовые файлы, DOC/DOCX и изображения. "
                "Если это PDF, пришлите текст или скриншоты страниц."
            )

    if caption:
        if text_context:
            doc_text_by_user[message.from_user.id] = text_context
            await message.answer("Документ получил, отвечаю по вашему вопросу.")
            await process_query(message, caption, extra_context=text_context)
        elif doc_images_by_user.get(message.from_user.id):
            await message.answer("Документ получил. Отвечаю по вашему вопросу.")
            await process_query(message, caption)
        else:
            await message.answer(
                "Документ получил, но текст не извлечен. Отвечу по вопросу, "
                "а для точности пришлите текстовые фрагменты."
            )
            await process_query(message, caption)
        return

    if text_context:
        doc_text_by_user[message.from_user.id] = text_context
        await message.answer(
            "Документ получен. Сформулируйте вопрос по нему — отвечу."
        )
    elif doc_images_by_user.get(message.from_user.id):
        await message.answer(
            "Документ получен. Сформулируйте вопрос — отвечу с учетом изображений."
        )
    else:
        await message.answer(
            "Документ получен. Напишите, что именно нужно выяснить, и приложите текстовые фрагменты."
        )

@router.message(F.text)
async def handle_question(message: Message):
    if message.text.startswith("/"):
        return

    user_id = message.from_user.id
    extra_context = doc_text_by_user.get(user_id, "")
    await process_query(message, message.text, extra_context=extra_context)
