"""
Helmitex Warehouse - Telegram бот для складского учета.
"""

__version__ = "1.0.1"
__author__ = "Helmitex Team"

from .config import settings

APP_NAME = settings.APP_NAME
APP_VERSION = settings.APP_VERSION

__all__ = ["settings", "APP_NAME", "APP_VERSION"]
