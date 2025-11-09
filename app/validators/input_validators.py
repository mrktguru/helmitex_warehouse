"""
Валидаторы пользовательского ввода для Helmitex Warehouse.

Модуль содержит все функции валидации данных, вводимых пользователем:
- Валидация чисел (количество, вес, проценты)
- Валидация текста (коды, названия)
- Парсинг и нормализация ввода
- Проверка диапазонов и форматов
"""
import re
from typing import Tuple, Optional
from decimal import Decimal, InvalidOperation
from app.logger import get_logger

logger = get_logger("input_validators")


# ============================================================================
# ВАЛИДАЦИЯ ЧИСЕЛ
# ============================================================================

def validate_quantity(
    input_text: str,
    min_value: float = 0.01,
    max_value: float = 999999.0,
    max_decimals: int = 2
) -> Tuple[bool, Optional[float], str]:
    """
    Валидация количества товара.
    
    Args:
        input_text: Введенный текст
        min_value: Минимальное допустимое значение
        max_value: Максимальное допустимое значение
        max_decimals: Максимальное количество знаков после запятой
        
    Returns:
        Tuple[bool, Optional[float], str]:
            - True если валидно
            - Распарсенное число или None
            - Сообщение об ошибке (если есть)
            
    Example:
        >>> validate_quantity("250.5")
        (True, 250.5, "")
        >>> validate_quantity("abc")
        (False, None, "Некорректный формат числа")
        >>> validate_quantity("0")
        (False, None, "Количество должно быть больше 0")
    """
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    
    # Парсим число
    is_valid, number = parse_float(input_text)
    
    if not is_valid:
        return False, None, "❌ Некорректный формат числа. Используйте цифры, точку или запятую."
    
    # Проверка минимума
    if number < min_value:
        return False, None, f"❌ Количество должно быть не менее {min_value}"
    
    # Проверка максимума
    if number > max_value:
        return False, None, f"❌ Количество не должно превышать {max_value}"
    
    # Проверка количества десятичных знаков
    decimal_places = count_decimal_places(number)
    if decimal_places > max_decimals:
        return False, None, f"❌ Максимум {max_decimals} знака после запятой"
    
    logger.debug(f"Валидация количества '{input_text}' → {number}")
    
    return True, number, ""


def validate_weight(
    input_text: str,
    min_weight: float = 0.1,
    max_weight: float = 9999.0,
    max_decimals: int = 1
) -> Tuple[bool, Optional[float], str]:
    """
    Валидация веса (более строгая чем quantity).
    
    Args:
        input_text: Введенный текст
        min_weight: Минимальный вес (кг)
        max_weight: Максимальный вес (кг)
        max_decimals: Максимальное количество знаков после запятой
        
    Returns:
        Tuple[bool, Optional[float], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_weight("150.5")
        (True, 150.5, "")
        >>> validate_weight("0.05")
        (False, None, "Вес должен быть не менее 0.1 кг")
    """
    return validate_quantity(
        input_text,
        min_value=min_weight,
        max_value=max_weight,
        max_decimals=max_decimals
    )


def validate_percentage(
    input_text: str,
    min_percent: float = 0.1,
    max_percent: float = 100.0,
    max_decimals: int = 2
) -> Tuple[bool, Optional[float], str]:
    """
    Валидация процента.
    
    Args:
        input_text: Введенный текст
        min_percent: Минимальный процент
        max_percent: Максимальный процент
        max_decimals: Максимальное количество знаков после запятой
        
    Returns:
        Tuple[bool, Optional[float], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_percentage("85.5")
        (True, 85.5, "")
        >>> validate_percentage("150")
        (False, None, "Процент не должен превышать 100")
    """
    is_valid, number = parse_float(input_text)
    
    if not is_valid:
        return False, None, "❌ Некорректный формат числа"
    
    if number < min_percent:
        return False, None, f"❌ Процент должен быть не менее {min_percent}"
    
    if number > max_percent:
        return False, None, f"❌ Процент не должен превышать {max_percent}"
    
    decimal_places = count_decimal_places(number)
    if decimal_places > max_decimals:
        return False, None, f"❌ Максимум {max_decimals} знака после запятой"
    
    logger.debug(f"Валидация процента '{input_text}' → {number}%")
    
    return True, number, ""


def validate_integer(
    input_text: str,
    min_value: int = 1,
    max_value: int = 99999
) -> Tuple[bool, Optional[int], str]:
    """
    Валидация целого числа.
    
    Args:
        input_text: Введенный текст
        min_value: Минимальное значение
        max_value: Максимальное значение
        
    Returns:
        Tuple[bool, Optional[int], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_integer("10")
        (True, 10, "")
        >>> validate_integer("abc")
        (False, None, "Введите целое число")
    """
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    
    text = input_text.strip()
    
    # Проверяем, что это целое число
    if not text.isdigit() and not (text.startswith('-') and text[1:].isdigit()):
        return False, None, "❌ Введите целое число (без дробной части)"
    
    try:
        number = int(text)
    except ValueError:
        return False, None, "❌ Некорректный формат числа"
    
    if number < min_value:
        return False, None, f"❌ Число должно быть не менее {min_value}"
    
    if number > max_value:
        return False, None, f"❌ Число не должно превышать {max_value}"
    
    logger.debug(f"Валидация целого числа '{input_text}' → {number}")
    
    return True, number, ""


# ============================================================================
# ВАЛИДАЦИЯ ТЕКСТА
# ============================================================================

def validate_code(
    input_text: str,
    min_length: int = 2,
    max_length: int = 50,
    allow_spaces: bool = False
) -> Tuple[bool, Optional[str], str]:
    """
    Валидация кода товара.
    
    Args:
        input_text: Введенный текст
        min_length: Минимальная длина
        max_length: Максимальная длина
        allow_spaces: Разрешить пробелы
        
    Returns:
        Tuple[bool, Optional[str], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_code("SKU-001")
        (True, "SKU-001", "")
        >>> validate_code("AB")
        (True, "AB", "")
        >>> validate_code("A")
        (False, None, "Код должен содержать минимум 2 символа")
    """
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите код"
    
    code = input_text.strip()
    
    # Проверка длины
    if len(code) < min_length:
        return False, None, f"❌ Код должен содержать минимум {min_length} символа"
    
    if len(code) > max_length:
        return False, None, f"❌ Код не должен превышать {max_length} символов"
    
    # Проверка на пробелы
    if not allow_spaces and ' ' in code:
        return False, None, "❌ Код не должен содержать пробелы"
    
    # Проверка на допустимые символы (буквы, цифры, дефис, подчеркивание)
    if not re.match(r'^[A-Za-zА-Яа-я0-9\-_]+$', code):
        return False, None, "❌ Код может содержать только буквы, цифры, дефис и подчеркивание"
    
    logger.debug(f"Валидация кода '{input_text}' → '{code}'")
    
    return True, code, ""


def validate_name(
    input_text: str,
    min_length: int = 2,
    max_length: int = 200,
    allow_special_chars: bool = True
) -> Tuple[bool, Optional[str], str]:
    """
    Валидация названия товара/категории.
    
    Args:
        input_text: Введенный текст
        min_length: Минимальная длина
        max_length: Максимальная длина
        allow_special_chars: Разрешить спецсимволы
        
    Returns:
        Tuple[bool, Optional[str], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_name("Краска белая акриловая")
        (True, "Краска белая акриловая", "")
        >>> validate_name("A")
        (False, None, "Название должно содержать минимум 2 символа")
    """
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите название"
    
    name = input_text.strip()
    
    # Проверка длины
    if len(name) < min_length:
        return False, None, f"❌ Название должно содержать минимум {min_length} символа"
    
    if len(name) > max_length:
        return False, None, f"❌ Название не должно превышать {max_length} символов"
    
    # Проверка на допустимые символы
    if not allow_special_chars:
        if not re.match(r'^[A-Za-zА-Яа-я0-9\s\-]+$', name):
            return False, None, "❌ Название может содержать только буквы, цифры, пробелы и дефис"
    
    logger.debug(f"Валидация названия '{input_text}' → '{name}'")
    
    return True, name, ""


def validate_notes(
    input_text: str,
    max_length: int = 500
) -> Tuple[bool, Optional[str], str]:
    """
    Валидация примечаний/заметок.
    
    Args:
        input_text: Введенный текст
        max_length: Максимальная длина
        
    Returns:
        Tuple[bool, Optional[str], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_notes("Дополнительная информация")
        (True, "Дополнительная информация", "")
        >>> validate_notes("")
        (True, "", "")
    """
    if not input_text:
        return True, "", ""
    
    text = input_text.strip()
    
    if len(text) > max_length:
        return False, None, f"❌ Примечание не должно превышать {max_length} символов"
    
    return True, text, ""


# ============================================================================
# ПАРСИНГ И НОРМАЛИЗАЦИЯ
# ============================================================================

def parse_float(input_text: str) -> Tuple[bool, Optional[float]]:
    """
    Парсинг float с поддержкой запятой как разделителя.
    
    Args:
        input_text: Введенный текст
        
    Returns:
        Tuple[bool, Optional[float]]: (успех, значение)
        
    Example:
        >>> parse_float("123.45")
        (True, 123.45)
        >>> parse_float("123,45")
        (True, 123.45)
        >>> parse_float("abc")
        (False, None)
    """
    if not input_text or not input_text.strip():
        return False, None
    
    # Заменяем запятую на точку
    text = input_text.strip().replace(',', '.')
    
    # Удаляем пробелы (могут быть разделителями тысяч)
    text = text.replace(' ', '')
    
    try:
        number = float(text)
        return True, number
    except (ValueError, InvalidOperation):
        logger.warning(f"Не удалось распарсить число: '{input_text}'")
        return False, None


def parse_integer(input_text: str) -> Tuple[bool, Optional[int]]:
    """
    Парсинг целого числа.
    
    Args:
        input_text: Введенный текст
        
    Returns:
        Tuple[bool, Optional[int]]: (успех, значение)
        
    Example:
        >>> parse_integer("123")
        (True, 123)
        >>> parse_integer("abc")
        (False, None)
    """
    if not input_text or not input_text.strip():
        return False, None
    
    text = input_text.strip().replace(' ', '')
    
    try:
        number = int(text)
        return True, number
    except ValueError:
        logger.warning(f"Не удалось распарсить целое число: '{input_text}'")
        return False, None


def normalize_text(input_text: str) -> str:
    """
    Нормализация текста (удаление лишних пробелов, приведение к единому формату).
    
    Args:
        input_text: Введенный текст
        
    Returns:
        str: Нормализованный текст
        
    Example:
        >>> normalize_text("  Текст   с    пробелами  ")
        "Текст с пробелами"
    """
    if not input_text:
        return ""
    
    # Удаляем пробелы в начале и конце
    text = input_text.strip()
    
    # Заменяем множественные пробелы на один
    text = re.sub(r'\s+', ' ', text)
    
    return text


# ============================================================================
# УТИЛИТЫ
# ============================================================================

def count_decimal_places(number: float) -> int:
    """
    Подсчет количества знаков после запятой.
    
    Args:
        number: Число
        
    Returns:
        int: Количество знаков после запятой
        
    Example:
        >>> count_decimal_places(123.45)
        2
        >>> count_decimal_places(123.0)
        0
    """
    # Конвертируем в строку через Decimal для точности
    decimal_num = Decimal(str(number))
    
    # Получаем строковое представление
    str_num = str(decimal_num)
    
    # Если есть точка, считаем знаки после неё
    if '.' in str_num:
        return len(str_num.split('.')[1])
    else:
        return 0


def is_positive_number(input_text: str) -> bool:
    """
    Проверка, является ли ввод положительным числом.
    
    Args:
        input_text: Введенный текст
        
    Returns:
        bool: True если положительное число
        
    Example:
        >>> is_positive_number("123.45")
        True
        >>> is_positive_number("-123")
        False
        >>> is_positive_number("abc")
        False
    """
    is_valid, number = parse_float(input_text)
    return is_valid and number > 0


def format_validation_error(field_name: str, error_message: str) -> str:
    """
    Форматирование сообщения об ошибке валидации.
    
    Args:
        field_name: Название поля
        error_message: Сообщение об ошибке
        
    Returns:
        str: Отформатированное сообщение
        
    Example:
        >>> format_validation_error("Количество", "должно быть положительным")
        "❌ Количество: должно быть положительным"
    """
    return f"❌ {field_name}: {error_message}"


# ============================================================================
# СПЕЦИФИЧНЫЕ ВАЛИДАТОРЫ
# ============================================================================

def validate_recipe_components(components_text: str) -> Tuple[bool, Optional[list], str]:
    """
    Валидация и парсинг компонентов рецепта.
    
    Формат ввода (каждая строка):
    "Название: процент" или "Категория / Название: процент"
    
    Args:
        components_text: Многострочный текст с компонентами
        
    Returns:
        Tuple[bool, Optional[list], str]:
            - True если валидно
            - Список компонентов [{'name': str, 'percentage': float}, ...]
            - Сообщение об ошибке
            
    Example:
        >>> validate_recipe_components("Мука: 60\\nВода: 30\\nСоль: 10")
        (True, [{'name': 'Мука', 'percentage': 60.0}, ...], "")
    """
    if not components_text or not components_text.strip():
        return False, None, "❌ Пожалуйста, введите компоненты рецепта"
    
    lines = components_text.strip().split('\n')
    components = []
    percentages = []
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        
        if not line:
            continue
        
        # Ожидаем формат "Название: процент"
        if ':' not in line:
            return False, None, f"❌ Строка {i}: неверный формат. Используйте 'Название: процент'"
        
        parts = line.split(':', 1)
        name = parts[0].strip()
        percentage_str = parts[1].strip()
        
        # Валидируем название
        if len(name) < 2:
            return False, None, f"❌ Строка {i}: название слишком короткое"
        
        # Валидируем процент
        is_valid, percentage = parse_float(percentage_str)
        if not is_valid:
            return False, None, f"❌ Строка {i}: некорректный процент '{percentage_str}'"
        
        if percentage <= 0 or percentage > 100:
            return False, None, f"❌ Строка {i}: процент должен быть от 0 до 100"
        
        components.append({
            'name': name,
            'percentage': percentage
        })
        percentages.append(percentage)
    
    if not components:
        return False, None, "❌ Не найдено ни одного компонента"
    
    # Проверяем сумму процентов
    total = sum(percentages)
    if abs(total - 100.0) > 0.1:
        return False, None, f"❌ Сумма процентов = {total:.1f}%, должна быть 100%"
    
    logger.info(f"Распарсено {len(components)} компонентов")
    
    return True, components, ""


def validate_yield_percent(input_text: str) -> Tuple[bool, Optional[float], str]:
    """
    Валидация процента выхода (50-100%).
    
    Args:
        input_text: Введенный текст
        
    Returns:
        Tuple[bool, Optional[float], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_yield_percent("85")
        (True, 85.0, "")
        >>> validate_yield_percent("110")
        (False, None, "Процент выхода должен быть от 50 до 100")
    """
    return validate_percentage(
        input_text,
        min_percent=50.0,
        max_percent=100.0,
        max_decimals=1
    )


def validate_telegram_id(input_text: str) -> Tuple[bool, Optional[int], str]:
    """
    Валидация Telegram ID.
    
    Args:
        input_text: Введенный текст
        
    Returns:
        Tuple[bool, Optional[int], str]: (валидно, значение, ошибка)
        
    Example:
        >>> validate_telegram_id("123456789")
        (True, 123456789, "")
        >>> validate_telegram_id("abc")
        (False, None, "Некорректный Telegram ID")
    """
    is_valid, number = parse_integer(input_text)
    
    if not is_valid:
        return False, None, "❌ Некорректный Telegram ID"
    
    # Telegram ID - положительное целое число
    if number <= 0:
        return False, None, "❌ Telegram ID должен быть положительным числом"
    
    # Обычно Telegram ID не больше 10 цифр
    if number > 9999999999:
        return False, None, "❌ Telegram ID слишком большой"
    
    return True, number, ""


# ============================================================================
# БЫСТРЫЕ ПРОВЕРКИ
# ============================================================================

def is_valid_quantity(text: str) -> bool:
    """Быстрая проверка валидности количества."""
    is_valid, _, _ = validate_quantity(text)
    return is_valid


def is_valid_weight(text: str) -> bool:
    """Быстрая проверка валидности веса."""
    is_valid, _, _ = validate_weight(text)
    return is_valid


def is_valid_percentage(text: str) -> bool:
    """Быстрая проверка валидности процента."""
    is_valid, _, _ = validate_percentage(text)
    return is_valid


def is_valid_integer(text: str) -> bool:
    """Быстрая проверка валидности целого числа."""
    is_valid, _, _ = validate_integer(text)
    return is_valid


def is_valid_code(text: str) -> bool:
    """Быстрая проверка валидности кода."""
    is_valid, _, _ = validate_code(text)
    return is_valid


def is_valid_name(text: str) -> bool:
    """Быстрая проверка валидности названия."""
    is_valid, _, _ = validate_name(text)
    return is_valid

def validate_positive_decimal(input_text: str, min_value: float = 0.01, max_value: float = 999999.0, max_decimals: int = 3):
    """Валидация положительного десятичного числа."""
    from typing import Tuple, Optional
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    is_valid, number = parse_float(input_text)
    if not is_valid:
        return False, None, "❌ Некорректный формат числа"
    if number <= 0:
        return False, None, "❌ Значение должно быть положительным"
    if number < min_value:
        return False, None, f"❌ Значение должно быть не менее {min_value}"
    if number > max_value:
        return False, None, f"❌ Значение не должно превышать {max_value}"
    decimal_places = count_decimal_places(number)
    if decimal_places > max_decimals:
        return False, None, f"❌ Максимум {max_decimals} знака после запятой"
    return True, number, ""

def validate_positive_integer(input_text: str, min_value: int = 1, max_value: int = 999999):
    """Валидация положительного целого числа."""
    from typing import Tuple, Optional
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    text = input_text.strip()
    if not text.isdigit():
        return False, None, "❌ Введите целое число"
    try:
        number = int(text)
    except ValueError:
        return False, None, "❌ Некорректный формат"
    if number <= 0:
        return False, None, "❌ Число должно быть положительным"
    if number < min_value or number > max_value:
        return False, None, f"❌ Число должно быть от {min_value} до {max_value}"
    return True, number, ""

def is_valid_positive_decimal(text: str):
    """Быстрая проверка."""
    is_valid, _, _ = validate_positive_decimal(text)
    return is_valid

def is_valid_positive_integer(text: str):
    """Быстрая проверка."""
    is_valid, _, _ = validate_positive_integer(text)
    return is_valid

# ============================================================================
# НЕДОСТАЮЩИЕ ФУНКЦИИ (ПАТЧ)
# ============================================================================

def validate_positive_decimal(input_text: str, min_value: float = 0.01, max_value: float = 999999.0, max_decimals: int = 3):
    """Валидация положительного десятичного числа."""
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    is_valid, number = parse_float(input_text)
    if not is_valid:
        return False, None, "❌ Некорректный формат числа"
    if number <= 0:
        return False, None, "❌ Значение должно быть положительным"
    if number < min_value:
        return False, None, f"❌ Значение должно быть не менее {min_value}"
    if number > max_value:
        return False, None, f"❌ Значение не должно превышать {max_value}"
    decimal_places = count_decimal_places(number)
    if decimal_places > max_decimals:
        return False, None, f"❌ Максимум {max_decimals} знака после запятой"
    return True, number, ""

def validate_positive_integer(input_text: str, min_value: int = 1, max_value: int = 999999):
    """Валидация положительного целого числа."""
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    text = input_text.strip()
    if not text.isdigit():
        return False, None, "❌ Введите целое число"
    try:
        number = int(text)
    except ValueError:
        return False, None, "❌ Некорректный формат"
    if number <= 0:
        return False, None, "❌ Число должно быть положительным"
    if number < min_value or number > max_value:
        return False, None, f"❌ Число должно быть от {min_value} до {max_value}"
    return True, number, ""

def validate_text_length(input_text: str, min_length: int = 1, max_length: int = 1000, field_name: str = "Текст"):
    """Валидация длины текста."""
    if not input_text:
        if min_length > 0:
            return False, None, f"❌ {field_name}: обязательное поле"
        return True, "", ""
    text = input_text.strip()
    text_len = len(text)
    if text_len < min_length:
        return False, None, f"❌ {field_name}: минимум {min_length} символов"
    if text_len > max_length:
        return False, None, f"❌ {field_name}: максимум {max_length} символов"
    return True, text, ""

def is_valid_positive_decimal(text: str):
    """Быстрая проверка."""
    is_valid, _, _ = validate_positive_decimal(text)
    return is_valid

def is_valid_positive_integer(text: str):
    """Быстрая проверка."""
    is_valid, _, _ = validate_positive_integer(text)
    return is_valid

def is_valid_text_length(text: str, min_length: int = 1, max_length: int = 1000):
    """Быстрая проверка."""
    is_valid, _, _ = validate_text_length(text, min_length, max_length)
    return is_valid

def parse_decimal_input(input_text: str):
    """
    Парсинг десятичного ввода (алиас для parse_float с возвратом в другом формате).
    
    Args:
        input_text: Введенный текст
        
    Returns:
        Tuple[bool, Optional[float], str]: (успех, значение, ошибка)
    """
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    
    is_valid, number = parse_float(input_text)
    
    if not is_valid:
        return False, None, "❌ Некорректный формат числа. Используйте цифры, точку или запятую."
    
    return True, number, ""

def parse_integer_input(input_text: str):
    """
    Парсинг целочисленного ввода.
    
    Args:
        input_text: Введенный текст
        
    Returns:
        Tuple[bool, Optional[int], str]: (успех, значение, ошибка)
    """
    if not input_text or not input_text.strip():
        return False, None, "❌ Пожалуйста, введите число"
    
    is_valid, number = parse_integer(input_text)
    
    if not is_valid:
        return False, None, "❌ Некорректный формат числа. Введите целое число."
    
    return True, number, ""

def validate_sku_code(input_text: str, min_length: int = 2, max_length: int = 50):
    """Валидация кода SKU (алиас для validate_code)."""
    return validate_code(input_text, min_length, max_length, allow_spaces=False)

def validate_sku_name(input_text: str, min_length: int = 2, max_length: int = 200):
    """Валидация названия SKU (алиас для validate_name)."""
    return validate_name(input_text, min_length, max_length, allow_special_chars=True)

def validate_warehouse_name(input_text: str, min_length: int = 2, max_length: int = 200):
    """Валидация названия склада (алиас для validate_name)."""
    return validate_name(input_text, min_length, max_length, allow_special_chars=True)

def validate_category_name(input_text: str, min_length: int = 2, max_length: int = 100):
    """Валидация названия категории (алиас для validate_name)."""
    return validate_name(input_text, min_length, max_length, allow_special_chars=False)

def validate_recipe_name(input_text: str, min_length: int = 3, max_length: int = 200):
    """Валидация названия рецепта (алиас для validate_name)."""
    return validate_name(input_text, min_length, max_length, allow_special_chars=True)

def validate_recipient_name(input_text: str, min_length: int = 2, max_length: int = 200):
    """Валидация имени получателя (алиас для validate_name)."""
    return validate_name(input_text, min_length, max_length, allow_special_chars=True)

def validate_contact_info(input_text: str, max_length: int = 500):
    """Валидация контактной информации (алиас для validate_notes)."""
    return validate_notes(input_text, max_length)

def validate_description(input_text: str, max_length: int = 1000):
    """Валидация описания (алиас для validate_notes)."""
    return validate_notes(input_text, max_length)
