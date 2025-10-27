"""
Вспомогательные функции.
"""
from typing import Dict, List, Any


def parse_key_value_lines(text: str) -> Dict[str, str]:
    """
    Парсит текст в формате "ключ: значение" в словарь.
    
    Args:
        text: Текст с парами ключ-значение (каждая пара на новой строке)
        
    Returns:
        Словарь с парами ключ-значение
        
    Example:
        >>> parse_key_value_lines("name: John\\nage: 30")
        {'name': 'John', 'age': '30'}
    """
    result = {}
    for line in text.strip().split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            result[key.strip()] = value.strip()
    return result


def format_sku_list(skus: List[Any]) -> str:
    """
    Форматирует список SKU для отображения в Telegram.
    
    Args:
        skus: Список объектов SKU
        
    Returns:
        Отформатированная строка
    """
    if not skus:
        return "📦 Список пуст"
    
    lines = ["📦 Список номенклатуры:\n"]
    for sku in skus:
        category = f" ({sku.category.name})" if sku.category else ""
        type_emoji = {
            "raw": "🌾",
            "semi": "⚙️",
            "finished": "✅"
        }.get(sku.type.value, "📦")
        
        lines.append(
            f"{type_emoji} {sku.code} - {sku.name} [{sku.type.value}]{category}"
        )
    
    return "\n".join(lines)


def format_recipe_list(recipes: List[Any]) -> str:
    """
    Форматирует список рецептов для отображения.
    
    Args:
        recipes: Список объектов Recipe
        
    Returns:
        Отформатированная строка
    """
    if not recipes:
        return "📋 Рецепты не найдены"
    
    lines = ["📋 Список рецептов:\n"]
    for recipe in recipes:
        product_name = recipe.semi_sku.name if recipe.semi_sku else "Неизвестно"
        status_emoji = {
            "draft": "📝",
            "active": "✅",
            "archived": "📦"
        }.get(recipe.status.value, "❓")
        
        lines.append(
            f"{status_emoji} ID:{recipe.id} - {product_name} "
            f"(выход: {recipe.theoretical_yield}%)"
        )
    
    return "\n".join(lines)


def format_category_list(categories: List[Any]) -> str:
    """
    Форматирует список категорий для отображения.
    
    Args:
        categories: Список объектов Category
        
    Returns:
        Отформатированная строка
    """
    if not categories:
        return "📁 Категории не найдены"
    
    lines = ["📁 Список категорий:\n"]
    for cat in categories:
        lines.append(f"• {cat.name}")
    
    return "\n".join(lines)


def format_barrel_list(barrels: List[Any]) -> str:
    """
    Форматирует список бочек для отображения.
    
    Args:
        barrels: Список объектов Barrel
        
    Returns:
        Отформатированная строка
    """
    if not barrels:
        return "🛢️ Бочки не найдены"
    
    lines = ["🛢️ Список бочек:\n"]
    for barrel in barrels:
        status_emoji = {
            "clean": "✨",
            "in_process": "⚙️",
            "ready": "✅",
            "washing": "🧼",
            "archived": "📦"
        }.get(barrel.status.value, "❓")
        
        lines.append(f"{status_emoji} {barrel.number} - {barrel.status.value}")
    
    return "\n".join(lines)


def format_weight(weight: float, unit: str = "кг") -> str:
    """
    Форматирует вес для отображения.
    
    Args:
        weight: Вес в числовом формате
        unit: Единица измерения
        
    Returns:
        Отформатированная строка
    """
    return f"{weight:.2f} {unit}"


def format_percentage(value: float) -> str:
    """
    Форматирует процент для отображения.
    
    Args:
        value: Значение в процентах
        
    Returns:
        Отформатированная строка
    """
    return f"{value:.1f}%"


def validate_percentage_sum(percentages: List[float], tolerance: float = 0.01) -> bool:
    """
    Проверяет, что сумма процентов равна 100% с учетом погрешности.
    
    Args:
        percentages: Список процентов
        tolerance: Допустимая погрешность
        
    Returns:
        True если сумма корректна
    """
    total = sum(percentages)
    return abs(total - 100.0) <= tolerance
