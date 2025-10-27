"""
Точка входа для запуска бота как модуля Python.
Использование: python -m helmitex_warehouse
"""
import sys
import logging

from helmitex_warehouse.bot import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)
