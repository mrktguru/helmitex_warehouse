from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import SKU, Category, SKUType, Recipe, RecipeComponent, RecipeStatus, Barrel, BarrelStatus, SemiBatch, ProductionUsedRaw

# Categories
def add_category(db: Session, name: str) -> Category:
    cat = Category(name=name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

def list_categories(db: Session) -> List[Category]:
    return db.execute(select(Category).order_by(Category.name)).scalars().all()

# SKU
def add_sku(db: Session, code: str, name: str, type_: SKUType, base_unit: str, pack_weight_g: Optional[float], category_name: Optional[str]) -> SKU:
    category = None
    if type_ == SKUType.raw:
        if not category_name:
            raise ValueError("Для сырья категория обязательна")
        category = db.execute(select(Category).where(Category.name == category_name)).scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория '{category_name}' не найдена")
    sku = SKU(code=code, name=name, type=type_, base_unit=base_unit, pack_weight_g=pack_weight_g, category=category, is_active=True)
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return sku

def find_sku_by_code(db: Session, code: str) -> Optional[SKU]:
    return db.execute(select(SKU).where(SKU.code == code)).scalar_one_or_none()

def list_skus(db: Session) -> List[SKU]:
    return db.execute(select(SKU).order_by(SKU.type, SKU.name)).scalars().all()

# Recipes (Tech Cards)
def create_recipe(db: Session, product_code: str, theoretical_yield_pct: float, components: List[Tuple[str, float]], status: RecipeStatus = RecipeStatus.active) -> Recipe:
    product = find_sku_by_code(db, product_code)
    if not product or product.type != SKUType.semi:
        raise ValueError("Неверный полуфабрикат (должен быть type=semi)")
    total = sum(p for _, p in components)
    if abs(total - 100.0) > 1e-9:
        raise ValueError("Сумма процентов должна быть 100%")

    recipe = Recipe(product_sku_id=product.id, theoretical_yield_pct=theoretical_yield_pct, status=status)
    db.add(recipe)
    db.flush()
    for category_name, percent in components:
        category = db.execute(select(Category).where(Category.name == category_name)).scalar_one_or_none()
        if not category:
            raise ValueError(f"Категория '{category_name}' не найдена")
        rc = RecipeComponent(recipe_id=recipe.id, category_id=category.id, percent=percent)
        db.add(rc)
    db.commit()
    db.refresh(recipe)
    return recipe

def get_active_recipe(db: Session, product_code: str) -> Optional[Recipe]:
    product = find_sku_by_code(db, product_code)
    if not product or product.type != SKUType.semi:
        return None
    return db.execute(select(Recipe).where(Recipe.product_sku_id == product.id, Recipe.status == RecipeStatus.active)).scalar_one_or_none()

def list_recipes(db: Session, status: Optional[RecipeStatus] = None) -> List[Recipe]:
    q = select(Recipe).order_by(Recipe.created_at.desc())
    if status:
        q = q.where(Recipe.status == status)
    return db.execute(q).scalars().all()

def activate_recipe(db: Session, recipe_id: int):
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise ValueError("Рецепт не найден")
    # Archive others for same product
    others = db.execute(select(Recipe).where(Recipe.product_sku_id == recipe.product_sku_id, Recipe.id != recipe.id, Recipe.status == RecipeStatus.active)).scalars().all()
    for r in others:
        r.status = RecipeStatus.archived
    recipe.status = RecipeStatus.active
    db.commit()

# Barrels
def ensure_barrel(db: Session, code: str) -> Barrel:
    barrel = db.execute(select(Barrel).where(Barrel.code == code)).scalar_one_or_none()
    if barrel:
        return barrel
    barrel = Barrel(code=code, status=BarrelStatus.clean)
    db.add(barrel)
    db.commit()
    db.refresh(barrel)
    return barrel

# Planning from target mass
def compute_plan_from_target_mass(target_mass_kg: float, theoretical_yield_pct: float, components: List[RecipeComponent]) -> Dict[str, float]:
    planned_input_kg = target_mass_kg / (theoretical_yield_pct / 100.0)
    plan = {}
    for rc in components:
        plan[rc.category.name] = planned_input_kg * (rc.percent / 100.0)
    return plan

# Production (Замес)
def produce_batch(
    db: Session,
    product_code: str,
    barrel_code: str,
    target_mass_kg: float,
    theoretical_yield_pct: float,
    used_raw: Dict[str, Tuple[str, float]],  # category -> (raw_sku_code, qty_kg)
    actual_mass_kg: float,
    maybe_new_recipe_components: Optional[List[Tuple[str, float]]] = None,
    save_new_recipe_draft: bool = False
) -> SemiBatch:
    product = find_sku_by_code(db, product_code)
    if not product or product.type != SKUType.semi:
        raise ValueError("Неверный полуфабрикат (type=semi)")
    barrel = ensure_barrel(db, barrel_code)

    # Validate replacements: only inside category
    for cat_name, (raw_code, qty) in used_raw.items():
        cat = db.execute(select(Category).where(Category.name == cat_name)).scalar_one_or_none()
        if not cat:
            raise ValueError(f"Категория '{cat_name}' не найдена")
        raw_sku = find_sku_by_code(db, raw_code)
        if not raw_sku or raw_sku.type != SKUType.raw:
            raise ValueError(f"Сырье '{raw_code}' не найдено или не сырьё")
        if not raw_sku.category_id or raw_sku.category_id != cat.id:
            raise ValueError(f"Замена вне категории запрещена: {raw_code} не из '{cat_name}'")

    planned_input_kg = target_mass_kg / (theoretical_yield_pct / 100.0)
    batch = SemiBatch(
        product_sku_id=product.id,
        barrel_id=barrel.id,
        recipe_id=None,
        target_mass_kg=target_mass_kg,
        planned_input_kg=planned_input_kg,
        theoretical_yield_pct=theoretical_yield_pct,
        actual_mass_kg=actual_mass_kg,
        remainder_kg=actual_mass_kg,
    )
    db.add(batch)
    db.flush()

    for cat_name, (raw_code, qty) in used_raw.items():
        cat = db.execute(select(Category).where(Category.name == cat_name)).scalar_one()
        raw_sku = find_sku_by_code(db, raw_code)
        db.add(ProductionUsedRaw(
            semi_batch_id=batch.id,
            category_id=cat.id,
            raw_sku_id=raw_sku.id,
            qty_kg=qty
        ))

    if save_new_recipe_draft and maybe_new_recipe_components:
        total = sum(p for _, p in maybe_new_recipe_components)
        if abs(total - 100.0) > 1e-9:
            raise ValueError("Сумма процентов новой ТК должна быть 100%")
        new_r = Recipe(product_sku_id=product.id, theoretical_yield_pct=theoretical_yield_pct, status=RecipeStatus.draft)
        db.add(new_r)
        db.flush()
        for cat_name, percent in maybe_new_recipe_components:
            cat = db.execute(select(Category).where(Category.name == cat_name)).scalar_one_or_none()
            if not cat:
                raise ValueError(f"Категория '{cat_name}' не найдена")
            db.add(RecipeComponent(recipe_id=new_r.id, category_id=cat.id, percent=percent))

    db.commit()
    db.refresh(batch)
    return batch
