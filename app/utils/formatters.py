"""
Форматирование данных для отображения в Telegram.
"""
from typing import List, Any
from datetime import datetime


def format_category_list(categories: List[Any]) -> str:
    """Форматирует список категорий."""
    if not categories:
        return "📁 Категории не найдены"
    
    lines = ["📁 *Список категорий:*\n"]
    for cat in categories:
        type_emoji = {
            "raw_material": "🌾",
            "semi_product": "⚙️",
            "finished_product": "📦"
        }.get(cat.type.value, "📁")
        
        lines.append(f"{type_emoji} {cat.name}")
    
    return "\n".join(lines)


def format_raw_material_list(materials: List[Any]) -> str:
    """Форматирует список сырья."""
    if not materials:
        return "🌾 Сырье не найдено"
    
    lines = ["🌾 *Сырье на складе:*\n"]
    for material in materials:
        stock_emoji = "✅" if material.stock_quantity > 0 else "⚠️"
        lines.append(
            f"{stock_emoji} *{material.category.name} / {material.name}*\n"
            f"   Остаток: {material.stock_quantity:.2f} {material.unit.value}"
        )
    
    return "\n".join(lines)


def format_semi_product_list(products: List[Any]) -> str:
    """Форматирует список полуфабрикатов."""
    if not products:
        return "⚙️ Полуфабрикаты не найдены"
    
    lines = ["⚙️ *Полуфабрикаты на складе:*\n"]
    for product in products:
        stock_emoji = "✅" if product.stock_quantity > 0 else "⚠️"
        lines.append(
            f"{stock_emoji} *{product.category.name} / {product.name}*\n"
            f"   Остаток: {product.stock_quantity:.2f} {product.unit.value}"
        )
    
    return "\n".join(lines)


def format_finished_product_list(products: List[Any]) -> str:
    """Форматирует список готовой продукции."""
    if not products:
        return "📦 Готовая продукция не найдена"
    
    lines = ["📦 *Готовая продукция на складе:*\n"]
    for product in products:
        stock_emoji = "✅" if product.stock_quantity > 0 else "⚠️"
        lines.append(
            f"{stock_emoji} *{product.category.name} / {product.name}*\n"
            f"   {product.package_type} {product.package_weight}кг\n"
            f"   Остаток: {int(product.stock_quantity)} шт"
        )
    
    return "\n".join(lines)


def format_recipe_list(recipes: List[Any]) -> str:
    """Форматирует список рецептов."""
    if not recipes:
        return "📋 Рецепты не найдены"
    
    lines = ["📋 *Технологические карты:*\n"]
    for recipe in recipes:
        status_emoji = {
            "draft": "📝",
            "active": "✅",
            "archived": "📦"
        }.get(recipe.status.value, "❓")
        
        lines.append(
            f"{status_emoji} *{recipe.name}*\n"
            f"   ID: {recipe.id}\n"
            f"   Продукт: {recipe.semi_product.name}\n"
            f"   Выход: {recipe.yield_percent}%\n"
            f"   Статус: {recipe.status.value}"
        )
    
    return "\n".join(lines)


def format_recipe_details(recipe: Any) -> str:
    """Форматирует детали рецепта."""
    lines = [
        f"📋 *Технологическая карта*\n",
        f"*Название:* {recipe.name}",
        f"*ID:* {recipe.id}",
        f"*Продукт:* {recipe.semi_product.category.name} / {recipe.semi_product.name}",
        f"*Выход:* {recipe.yield_percent}%",
        f"*Статус:* {recipe.status.value}\n",
        f"*Состав:*"
    ]
    
    for component in recipe.components:
        lines.append(
            f"• {component.raw_material.category.name} / {component.raw_material.name}: "
            f"{component.percentage:.1f}%"
        )
    
    if recipe.description:
        lines.append(f"\n*Описание:* {recipe.description}")
    
    return "\n".join(lines)


def format_materials_check(check_result: dict) -> str:
    """Форматирует результат проверки наличия сырья."""
    lines = ["📊 *Проверка наличия сырья:*\n"]
    
    for material in check_result["materials"]:
        status_emoji = "✅" if material["is_available"] else "❌"
        lines.append(
            f"{status_emoji} *{material['category']} / {material['name']}*\n"
            f"   Требуется: {material['required']:.2f} {material['unit']}\n"
            f"   Доступно: {material['available_stock']:.2f} {material['unit']}"
        )
    
    if check_result["available"]:
        lines.append("\n✅ *Все сырье в наличии, можно начинать производство!*")
    else:
        lines.append("\n❌ *Недостаточно сырья для производства*")
    
    return "\n".join(lines)


def format_movement_history(movements: List[Any]) -> str:
    """Форматирует историю движений склада."""
    if not movements:
        return "📊 История операций пуста"
    
    lines = ["📊 *История операций:*\n"]
    
    for movement in movements:
        date_str = movement.created_at.strftime("%d.%m.%Y %H:%M")
        
        type_emoji = {
            "arrival": "📥",
            "production": "⚙️",
            "production_output": "✅",
            "packing": "📦",
            "packing_output": "✅",
            "shipment": "🚚"
        }.get(movement.movement_type.value, "📊")
        
        # Определяем что за материал
        item_name = ""
        if movement.raw_material:
            item_name = f"{movement.raw_material.category.name} / {movement.raw_material.name}"
        elif movement.semi_product:
            item_name = f"{movement.semi_product.category.name} / {movement.semi_product.name}"
        elif movement.finished_product:
            item_name = f"{movement.finished_product.category.name} / {movement.finished_product.name}"
        
        qty_str = f"{movement.quantity:+.2f}" if movement.quantity < 100 else f"{int(movement.quantity):+d}"
        
        lines.append(
            f"{type_emoji} *{date_str}*\n"
            f"   {item_name}\n"
            f"   Количество: {qty_str}"
        )
    
    return "\n".join(lines)


def format_date(dt: datetime) -> str:
    """Форматирует дату."""
    return dt.strftime("%d.%m.%Y %H:%M")


def format_weight(weight: float, unit: str = "кг") -> str:
    """Форматирует вес."""
    return f"{weight:.2f} {unit}"


def format_percentage(value: float) -> str:
    """Форматирует процент."""
    return f"{value:.1f}%"
