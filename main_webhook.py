import asyncio
import logging
import os
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.config import config
from bot.handlers import router

logging.basicConfig(level=logging.INFO)

async def on_startup(app):
    logging.info("Webhook запущен!")

async def on_shutdown(app):
    logging.warning("Webhook остановлен.")

async def main():
    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.include_router(router)
    
    # Создаём веб-приложение
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Настраиваем обработчик webhook
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    
    # !!! ИСПРАВЛЕНИЕ ЗДЕСЬ !!!
    # Регистрируем обработчик на конкретный путь
    webhook_requests_handler.register(app, path="/webhook")
    
    # Настраиваем приложение (связываем app и dispatcher)
    setup_application(app, dp, bot=bot)

    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    
    logging.info(f"Webhook сервер запущен на порту {port}")
    
    # Держим сервер запущенным бесконечно
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
