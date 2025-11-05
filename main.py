# main.py
"""
Точка входа приложения - Telegram-бот для управления складом.

Основные функции:
- Инициализация всех компонентов (логирование, БД, бот)
- Регистрация handlers и middleware
- Запуск бота в режиме polling
- Graceful shutdown при остановке
- Обработка сигналов SIGINT/SIGTERM

Запуск:
    python main.py
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.database.connection import init_db, close_db, create_tables
from app.middleware.database import setup_middleware
from app.utils.logger import setup_logging, get_logger
from app.bot import register_handlers, setup_bot_commands

# Флаг для graceful shutdown
shutdown_event = asyncio.Event()


def handle_shutdown_signal(signum, frame):
    """
    Обработчик сигналов завершения (SIGINT, SIGTERM).
    
    Args:
        signum: Номер сигнала
        frame: Текущий фрейм выполнения
    """
    logger = get_logger(__name__)
    logger.info(f"⚠️ Получен сигнал завершения: {signal.Signals(signum).name}")
    shutdown_event.set()


@asynccontextmanager
async def lifespan():
    """
    Контекстный менеджер для управления жизненным циклом приложения.
    
    Выполняет:
    - Инициализацию при старте
    - Корректное завершение при остановке
    
    Yields:
        None: Контроль выполнения основному коду
    """
    logger = get_logger(__name__)
    
    try:
        # ========== ИНИЦИАЛИЗАЦИЯ ==========
        logger.info("=" * 60)
        logger.info("🚀 Запуск приложения: Система управления складом")
        logger.info("=" * 60)
        
        # 1. Инициализация базы данных
        logger.info("📊 Инициализация базы данных...")
        await init_db()
        
        # 2. Создание таблиц (только в dev режиме, если БД пустая)
        if settings.APP_ENV == "development" and settings.AUTO_CREATE_TABLES:
            logger.warning("⚠️ AUTO_CREATE_TABLES включен - создание таблиц...")
            await create_tables()
        
        logger.info("✅ Инициализация завершена успешно")
        logger.info("=" * 60)
        
        # Передаем управление основному коду
        yield
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при инициализации: {e}", exc_info=True)
        raise
    
    finally:
        # ========== ЗАВЕРШЕНИЕ ==========
        logger.info("=" * 60)
        logger.info("🛑 Остановка приложения...")
        logger.info("=" * 60)
        
        # Закрываем подключение к БД
        logger.info("📊 Закрытие подключения к базе данных...")
        await close_db()
        
        logger.info("✅ Приложение остановлено корректно")
        logger.info("=" * 60)


async def create_bot() -> Bot:
    """
    Создает и настраивает экземпляр бота.
    
    Returns:
        Bot: Настроенный экземпляр бота
    """
    logger = get_logger(__name__)
    
    # Создаем бота с настройками по умолчанию
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,  # HTML разметка по умолчанию
        ),
    )
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    logger.info(f"🤖 Бот создан: @{bot_info.username} (ID: {bot_info.id})")
    
    return bot


def create_dispatcher() -> Dispatcher:
    """
    Создает и настраивает dispatcher.
    
    Returns:
        Dispatcher: Настроенный dispatcher
    """
    logger = get_logger(__name__)
    
    # Создаем dispatcher с хранилищем состояний в памяти
    # Для production рекомендуется использовать Redis storage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    logger.info("📦 Dispatcher создан с MemoryStorage")
    
    # Регистрируем middleware
    logger.info("🔧 Регистрация middleware...")
    setup_middleware(dp)
    
    # Регистрируем handlers
    logger.info("🔧 Регистрация handlers...")
    register_handlers(dp)
    
    logger.info("✅ Dispatcher настроен")
    
    return dp


async def main():
    """
    Главная функция приложения.
    
    Выполняет:
    1. Настройку логирования
    2. Инициализацию компонентов
    3. Запуск бота
    4. Обработку завершения
    """
    # ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
    setup_logging()
    logger = get_logger(__name__)
    
    # ========== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ СИГНАЛОВ ==========
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    logger.info("✅ Обработчики сигналов зарегистрированы (SIGINT, SIGTERM)")
    
    # ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
    async with lifespan():
        try:
            # Создаем бота и dispatcher
            bot = await create_bot()
            dp = create_dispatcher()
            
            # Настраиваем команды бота (ДО запуска polling!)
            logger.info("⚙️ Настройка команд бота...")
            try:
                await setup_bot_commands(bot)
                logger.info("✅ Команды бота настроены")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка настройки команд: {e}")
            
            # Удаляем webhook (если был установлен ранее)
            await bot.delete_webhook(drop_pending_updates=settings.DROP_PENDING_UPDATES)
            logger.info("✅ Webhook удален (если был установлен)")
            
            # Информация о режиме работы
            logger.info("=" * 60)
            logger.info(f"🌍 Окружение: {settings.APP_ENV.upper()}")
            logger.info(f"🔐 Админы: {settings.ADMIN_IDS}")
            logger.info(f"⏰ Часовой пояс: {settings.TIMEZONE}")
            logger.info(f"📝 Уровень логирования: {settings.LOG_LEVEL}")
            logger.info("=" * 60)
            
            # Запускаем polling
            logger.info("🚀 Запуск polling...")
            logger.info("💬 Бот готов к приему сообщений!")
            logger.info("=" * 60)
            
            # Создаем задачу для polling
            polling_task = asyncio.create_task(
                dp.start_polling(
                    bot,
                    allowed_updates=dp.resolve_used_update_types(),
                    handle_signals=False,  # Мы сами обрабатываем сигналы
                )
            )
            
            # Ждем сигнала завершения
            await shutdown_event.wait()
            
            # Останавливаем polling
            logger.info("⏹️ Остановка polling...")
            polling_task.cancel()
            
            try:
                await polling_task
            except asyncio.CancelledError:
                logger.info("✅ Polling остановлен")

            # Закрываем сессию бота
            await bot.session.close()
            logger.info("✅ Сессия бота закрыта")
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в main(): {e}", exc_info=True)
            raise


async def webhook_main():
    """
    Альтернативная функция для запуска бота в режиме webhook.
    
    Используется для деплоя на серверах с обратным прокси (nginx).
    Требует дополнительной настройки webhook URL и SSL сертификата.
    
    Note:
        Для использования webhook измените вызов в __main__ блоке.
    """
    logger = get_logger(__name__)
    
    # Проверяем наличие настроек webhook
    if not hasattr(settings, 'WEBHOOK_URL') or not settings.WEBHOOK_URL:
        logger.error("❌ WEBHOOK_URL не настроен в конфигурации!")
        return
    
    async with lifespan():
        try:
            bot = await create_bot()
            dp = create_dispatcher()
            
            # Устанавливаем webhook
            webhook_url = f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=settings.DROP_PENDING_UPDATES,
            )
            logger.info(f"✅ Webhook установлен: {webhook_url}")
            
            # Здесь должен быть код для запуска веб-сервера (aiohttp, FastAPI и т.д.)
            logger.warning("⚠️ Webhook режим требует дополнительной реализации веб-сервера!")
            logger.info("📖 См. документацию aiogram для настройки webhook")
            
            # Ждем сигнала завершения
            await shutdown_event.wait()
            
            # Удаляем webhook
            await bot.delete_webhook()
            logger.info("✅ Webhook удален")
            
            await bot.session.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка в webhook_main(): {e}", exc_info=True)
            raise


def run():
    """
    Обертка для запуска async функции main().
    
    Использует asyncio.run() для запуска event loop.
    """
    try:
        # Запускаем основную async функцию
        asyncio.run(main())
    except KeyboardInterrupt:
        # Ctrl+C нажат - корректное завершение
        logger = get_logger(__name__)
        logger.info("⌨️ KeyboardInterrupt - завершение работы...")
    except Exception as e:
        # Неожиданная ошибка
        logger = get_logger(__name__)
        logger.critical(f"💥 Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    """
    Точка входа при запуске скрипта напрямую.
    
    Запуск:
        python main.py
    
    Для webhook режима замените main() на webhook_main():
        asyncio.run(webhook_main())
    """
    # Проверяем версию Python
    if sys.version_info < (3, 11):
        print("❌ Требуется Python 3.11 или выше!")
        print(f"   Текущая версия: {sys.version}")
        sys.exit(1)
    
    # Выводим информацию о запуске
    print("=" * 60)
    print("🏭 Система управления складом - Производство краски и шпатлевки")
    print("=" * 60)
    print(f"🐍 Python: {sys.version.split()[0]}")
    print(f"🌍 Окружение: {settings.APP_ENV.upper()}")
    print(f"🤖 Telegram Bot API")
    print("=" * 60)
    print()
    
    # Запускаем приложение
    run()
