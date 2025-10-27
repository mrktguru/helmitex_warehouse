"""
Сервисы для работы с бизнес-логикой.
Временный файл - будет разделен на модули.
"""
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models import (
    SKU, Category, SKUType, Recipe, RecipeComponent, RecipeStatus,
    Barrel, BarrelStatus, SemiBatch, ProductionUsedRaw, Production
)


# Categories
def add_category(db: Session, name: str) -> Category:
    """Добавить категорию сырья."""
    category = Category(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_categories(db: Session) -> List[Category]:
    """Получить список всех категорий."""
    return db.execute(select(Category)).scalars().all()


def find_category_by_name(db: Session, name: str) -> Optional[Category]:
    """Найти категорию по имени."""
    return db.execute(select(Category).where(Category.name == name)).scalar_one_or_none()


# SKUs
def add_sku(
    db: Session,
    code: str,
    name: str,
    sku_type: SKUType,
    unit: str,
    package_weight: Optional[float] = None,
    category_id: Optional[int] = None
) -> SKU:
    """Добавить номенклатуру."""
    sku = SKU(
        code=code,
        name=name,
        type=sku_type,
        unit=unit,
        package_weight=package_weight,
        category_id=category_id
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku


def list_skus(db: Session, sku_type: Optional[SKUType] = None) -> List[SKU]:
    """Получить список номенклатуры."""
    query = select(SKU)
    if sku_type:
        query = query.where(SKU.type == sku_type)
    return db.execute(query).scalars().all()


def find_sku_by_code(db: Session, code: str) -> Optional[SKU]:
    """Найти SKU по коду."""
    return db.execute(select(SKU).where(SKU.code == code)).scalar_one_or_none()


# Recipes
def create_recipe(
    db: Session,
    semi_sku_id: int,
    theoretical_yield: float,
    components: List[Dict[str, float]],
    status: RecipeStatus = RecipeStatus.draft
) -> Recipe:
    """
    Создать рецепт.
    
    Args:
        db: Сессия БД
        semi_sku_id: ID полуфабриката
        theoretical_yield: Теоретический выход (%)
        components: Список компонентов [{"raw_sku_id": 1, "percentage": 50.0}, ...]
        status: Статус рецепта
    """
    recipe = Recipe(
        semi_sku_id=semi_sku_id,
        theoretical_yield=theoretical_yield,
        status=status
    )
    db.add(recipe)
    db.flush()
    
    for comp in components:
        recipe_comp = RecipeComponent(
            recipe_id=recipe.id,
            raw_sku_id=comp["raw_sku_id"],
            percentage=comp["percentage"]
        )
        db.add(recipe_comp)
    
    db.commit()
    db.refresh(recipe)
    return recipe


def list_recipes(db: Session, status: Optional[RecipeStatus] = None) -> List[Recipe]:
    """Получить список рецептов."""
    query = select(Recipe)
    if status:
        query = query.where(Recipe.status == status)
    return db.execute(query).scalars().all()


def get_recipe_by_id(db: Session, recipe_id: int) -> Optional[Recipe]:
    """Получить рецепт по ID."""
    return db.execute(select(Recipe).where(Recipe.id == recipe_id)).scalar_one_or_none()


def activate_recipe(db: Session, recipe_id: int) -> Recipe:
    """Активировать рецепт."""
    recipe = get_recipe_by_id(db, recipe_id)
    if recipe:
        recipe.status = RecipeStatus.active
        db.commit()
        db.refresh(recipe)
    return recipe


# Barrels
def add_barrel(db: Session, number: str) -> Barrel:
    """Добавить бочку."""
    barrel = Barrel(number=number, status=BarrelStatus.clean)
    db.add(barrel)
    db.commit()
    db.refresh(barrel)
    return barrel


def list_barrels(db: Session, status: Optional[BarrelStatus] = None) -> List[Barrel]:
    """Получить список бочек."""
    query = select(Barrel)
    if status:
        query = query.where(Barrel.status == status)
    return db.execute(query).scalars().all()


def get_barrel_by_id(db: Session, barrel_id: int) -> Optional[Barrel]:
    """Получить бочку по ID."""
    return db.execute(select(Barrel).where(Barrel.id == barrel_id)).scalar_one_or_none()


def update_barrel_status(db: Session, barrel_id: int, status: BarrelStatus) -> Barrel:
    """Обновить статус бочки."""
    barrel = get_barrel_by_id(db, barrel_id)
    if barrel:
        barrel.status = status
        db.commit()
        db.refresh(barrel)
    return barrel


# Production
def start_production(
    db: Session,
    recipe_id: int,
    barrel_id: int,
    operator_telegram_id: int,
    target_weight: float
) -> Production:
    """Начать производство."""
    production = Production(
        recipe_id=recipe_id,
        barrel_id=barrel_id,
        operator_telegram_id=operator_telegram_id,
        target_weight=target_weight
    )
    db.add(production)
    
    # Обновляем статус бочки
    update_barrel_status(db, barrel_id, BarrelStatus.in_process)
    
    db.commit()
    db.refresh(production)
    return production


def save_production(
    db: Session,
    production_id: int,
    actual_weight: float,
    used_raw: List[Dict[str, float]]
) -> Production:
    """
    Сохранить результаты производства.
    
    Args:
        db: Сессия БД
        production_id: ID производства
        actual_weight: Фактический вес
        used_raw: Использованное сырье [{"raw_sku_id": 1, "weight": 10.5}, ...]
    """
    production = db.execute(
        select(Production).where(Production.id == production_id)
    ).scalar_one_or_none()
    
    if production:
        production.actual_weight = actual_weight
        from datetime import datetime
        production.completed_at = datetime.utcnow()
        
        for raw in used_raw:
            prod_raw = ProductionUsedRaw(
                production_id=production_id,
                raw_sku_id=raw["raw_sku_id"],
                weight=raw["weight"]
            )
            db.add(prod_raw)
        
        # Обновляем статус бочки
        update_barrel_status(db, production.barrel_id, BarrelStatus.ready)
        
        db.commit()
        db.refresh(production)
    
    return production


def list_productions(db: Session, limit: int = 50) -> List[Production]:
    """Получить список производств."""
    return db.execute(
        select(Production).order_by(Production.created_at.desc()).limit(limit)
    ).scalars().all()
