"""
Сервис для работы с технологическими картами (рецептами).
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import Recipe, RecipeComponent, RecipeStatus, SemiProduct, RawMaterial
from app.exceptions import RecipeNotFoundError, RecipeValidationError, ValidationError
from app.logger import get_logger

logger = get_logger("recipe_service")


def create_recipe(
    db: Session,
    name: str,
    semi_product_id: int,
    yield_percent: float,
    components: List[Dict[str, float]],
    created_by: int,
    description: Optional[str] = None
) -> Recipe:
    """
    Создать новую технологическую карту.
    
    Args:
        db: Сессия БД
        name: Название ТК
        semi_product_id: ID полуфабриката
        yield_percent: Процент выхода (50-100%)
        components: Список компонентов [{"raw_material_id": 1, "percentage": 50.0}, ...]
        created_by: Telegram ID создателя
        description: Описание (опционально)
        
    Returns:
        Созданная ТК
        
    Raises:
        RecipeValidationError: Если данные некорректны
    """
    # Проверка процента выхода
    if not (50 <= yield_percent <= 100):
        raise RecipeValidationError("Процент выхода должен быть от 50% до 100%")
    
    # Проверка что полуфабрикат существует
    semi_product = db.execute(
        select(SemiProduct).where(SemiProduct.id == semi_product_id)
    ).scalar_one_or_none()
    
    if not semi_product:
        raise ValidationError(f"Полуфабрикат с ID {semi_product_id} не найден")
    
    # Проверка компонентов
    if not components:
        raise RecipeValidationError("Рецепт должен содержать хотя бы один компонент")
    
    total_percentage = sum(comp["percentage"] for comp in components)
    if abs(total_percentage - 100.0) > 0.01:
        raise RecipeValidationError(
            f"Сумма процентов компонентов должна быть 100%. "
            f"Текущая сумма: {total_percentage:.2f}%"
        )
    
    # Проверка что все компоненты существуют
    for comp in components:
        material = db.execute(
            select(RawMaterial).where(RawMaterial.id == comp["raw_material_id"])
        ).scalar_one_or_none()
        
        if not material:
            raise ValidationError(f"Сырье с ID {comp['raw_material_id']} не найдено")
    
    # Создаем рецепт
    recipe = Recipe(
        name=name,
        semi_product_id=semi_product_id,
        yield_percent=yield_percent,
        status=RecipeStatus.draft,
        description=description,
        created_by=created_by
    )
    
    db.add(recipe)
    db.flush()
    
    # Добавляем компоненты
    for comp in components:
        recipe_comp = RecipeComponent(
            recipe_id=recipe.id,
            raw_material_id=comp["raw_material_id"],
            percentage=comp["percentage"]
        )
        db.add(recipe_comp)
    
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"Создана ТК: {name} (ID: {recipe.id}, полуфабрикат: {semi_product.name})")
    return recipe


def get_recipes(
    db: Session,
    status: Optional[RecipeStatus] = None,
    semi_product_id: Optional[int] = None
) -> List[Recipe]:
    """
    Получить список рецептов.
    
    Args:
        db: Сессия БД
        status: Фильтр по статусу (опционально)
        semi_product_id: Фильтр по полуфабрикату (опционально)
        
    Returns:
        Список рецептов
    """
    query = select(Recipe).order_by(Recipe.name)
    
    if status:
        query = query.where(Recipe.status == status)
    
    if semi_product_id:
        query = query.where(Recipe.semi_product_id == semi_product_id)
    
    recipes = db.execute(query).scalars().all()
    return list(recipes)


def get_recipe_by_id(db: Session, recipe_id: int) -> Recipe:
    """
    Получить рецепт по ID.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        Рецепт
        
    Raises:
        RecipeNotFoundError: Если рецепт не найден
    """
    recipe = db.execute(
        select(Recipe).where(Recipe.id == recipe_id)
    ).scalar_one_or_none()
    
    if not recipe:
        raise RecipeNotFoundError(recipe_id)
    
    return recipe


def activate_recipe(db: Session, recipe_id: int) -> Recipe:
    """
    Активировать рецепт (только для администратора).
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        Активированный рецепт
    """
    recipe = get_recipe_by_id(db, recipe_id)
    recipe.status = RecipeStatus.active
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"Активирована ТК ID {recipe_id}: {recipe.name}")
    return recipe


def archive_recipe(db: Session, recipe_id: int) -> Recipe:
    """
    Архивировать рецепт.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        
    Returns:
        Архивированный рецепт
    """
    recipe = get_recipe_by_id(db, recipe_id)
    recipe.status = RecipeStatus.archived
    db.commit()
    db.refresh(recipe)
    
    logger.info(f"Архивирована ТК ID {recipe_id}: {recipe.name}")
    return recipe


def calculate_materials_needed(
    db: Session,
    recipe_id: int,
    target_weight: float
) -> Dict[int, float]:
    """
    Рассчитать необходимое количество сырья для производства.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        target_weight: Целевой вес полуфабриката
        
    Returns:
        Словарь {raw_material_id: required_weight}
    """
    recipe = get_recipe_by_id(db, recipe_id)
    
    materials_needed = {}
    
    for component in recipe.components:
        # Рассчитываем необходимое количество с учетом процента выхода
        required_weight = (target_weight / recipe.yield_percent * 100) * (component.percentage / 100)
        materials_needed[component.raw_material_id] = required_weight
    
    return materials_needed


def check_materials_availability(
    db: Session,
    recipe_id: int,
    target_weight: float
) -> Dict[str, any]:
    """
    Проверить наличие сырья для производства.
    
    Args:
        db: Сессия БД
        recipe_id: ID рецепта
        target_weight: Целевой вес полуфабриката
        
    Returns:
        Словарь с информацией о доступности материалов
    """
    materials_needed = calculate_materials_needed(db, recipe_id, target_weight)
    
    result = {
        "available": True,
        "materials": []
    }
    
    for material_id, required_qty in materials_needed.items():
        material = db.execute(
            select(RawMaterial).where(RawMaterial.id == material_id)
        ).scalar_one()
        
        available = material.stock_quantity >= required_qty
        
        result["materials"].append({
            "id": material_id,
            "name": material.name,
            "category": material.category.name,
            "required": required_qty,
            "available_stock": material.stock_quantity,
            "unit": material.unit.value,
            "is_available": available
        })
        
        if not available:
            result["available"] = False
    
    return result
