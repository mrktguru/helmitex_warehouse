"""
Модели базы данных для складского учета Helmitex Warehouse.
Переработанная версия с простой логикой учета.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Float, Boolean, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum

from app.database.db import Base


# ============================================================================
# ENUMS (Перечисления)
# ============================================================================

class CategoryType(str, enum.Enum):
    """Типы категорий."""
    raw_material = "raw_material"      # Категория сырья
    semi_product = "semi_product"      # Категория полуфабрикатов
    finished_product = "finished_product"  # Категория готовой продукции


class UnitType(str, enum.Enum):
    """Единицы измерения."""
    kg = "кг"
    liter = "л"
    piece = "шт"
    gram = "г"
    ml = "мл"


class RecipeStatus(str, enum.Enum):
    """Статусы технологических карт."""
    draft = "draft"          # Черновик
    active = "active"        # Активная
    archived = "archived"    # Архивная


class MovementType(str, enum.Enum):
    """Типы движений склада."""
    arrival = "arrival"              # Приход сырья
    production = "production"        # Производство (списание сырья)
    production_output = "production_output"  # Производство (выход полуфабриката)
    packing = "packing"              # Фасовка (списание полуфабриката)
    packing_output = "packing_output"  # Фасовка (выход готовой продукции)
    shipment = "shipment"            # Отгрузка
    adjustment = "adjustment"        # Корректировка остатков


# ============================================================================
# СПРАВОЧНИКИ
# ============================================================================

class Category(Base):
    """Категории (универсальные для сырья, полуфабрикатов, продукции)."""
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[CategoryType] = mapped_column(Enum(CategoryType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)  # Telegram ID
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    raw_materials = relationship("RawMaterial", back_populates="category")
    semi_products = relationship("SemiProduct", back_populates="category")
    finished_products = relationship("FinishedProduct", back_populates="category")


class RawMaterial(Base):
    """Сырье."""
    __tablename__ = "raw_materials"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[UnitType] = mapped_column(Enum(UnitType), nullable=False)
    stock_quantity: Mapped[float] = mapped_column(Float, default=0.0)  # Текущий остаток
    min_stock: Mapped[float] = mapped_column(Float, nullable=True)  # Минимальный остаток (для уведомлений)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="raw_materials")
    recipe_components = relationship("RecipeComponent", back_populates="raw_material")
    movements = relationship("StockMovement", 
                           foreign_keys="[StockMovement.raw_material_id]",
                           back_populates="raw_material")


class SemiProduct(Base):
    """Полуфабрикаты."""
    __tablename__ = "semi_products"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[UnitType] = mapped_column(Enum(UnitType), nullable=False)
    stock_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="semi_products")
    recipes = relationship("Recipe", back_populates="semi_product")
    movements = relationship("StockMovement",
                           foreign_keys="[StockMovement.semi_product_id]",
                           back_populates="semi_product")


class FinishedProduct(Base):
    """Готовая продукция."""
    __tablename__ = "finished_products"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    package_type: Mapped[str] = mapped_column(String(100), nullable=False)  # Тип тары (пакет, банка и т.д.)
    package_weight: Mapped[float] = mapped_column(Float, nullable=False)  # Вес упаковки
    unit: Mapped[UnitType] = mapped_column(Enum(UnitType), default=UnitType.piece)  # Обычно "шт"
    stock_quantity: Mapped[float] = mapped_column(Float, default=0.0)  # Количество упаковок
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="finished_products")
    movements = relationship("StockMovement",
                           foreign_keys="[StockMovement.finished_product_id]",
                           back_populates="finished_product")


# ============================================================================
# ТЕХНОЛОГИЧЕСКИЕ КАРТЫ
# ============================================================================

class Recipe(Base):
    """Технологическая карта (рецепт производства полуфабриката)."""
    __tablename__ = "recipes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    semi_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("semi_products.id"), nullable=False)
    yield_percent: Mapped[float] = mapped_column(Float, nullable=False)  # Процент выхода (50-100%)
    status: Mapped[RecipeStatus] = mapped_column(Enum(RecipeStatus), default=RecipeStatus.draft)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    semi_product = relationship("SemiProduct", back_populates="recipes")
    components = relationship("RecipeComponent", back_populates="recipe", cascade="all, delete-orphan")
    productions = relationship("Production", back_populates="recipe")


class RecipeComponent(Base):
    """Компоненты технологической карты."""
    __tablename__ = "recipe_components"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"), nullable=False)
    raw_material_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_materials.id"), nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)  # Процент в рецепте
    
    # Relationships
    recipe = relationship("Recipe", back_populates="components")
    raw_material = relationship("RawMaterial", back_populates="recipe_components")


# ============================================================================
# ОПЕРАЦИИ
# ============================================================================

class Production(Base):
    """Производство (замес) полуфабриката."""
    __tablename__ = "productions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"), nullable=False)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False)  # Целевой вес полуфабриката
    actual_weight: Mapped[float] = mapped_column(Float, nullable=True)  # Фактический вес
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)  # Telegram ID оператора
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Relationships
    recipe = relationship("Recipe", back_populates="productions")


class Packing(Base):
    """Фасовка полуфабриката в готовую продукцию."""
    __tablename__ = "packings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    semi_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("semi_products.id"), nullable=False)
    finished_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("finished_products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # Количество упаковок
    weight_used: Mapped[float] = mapped_column(Float, nullable=False)  # Использовано полуфабриката (кг/л)
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str] = mapped_column(Text, nullable=True)


class Shipment(Base):
    """Отгрузка готовой продукции."""
    __tablename__ = "shipments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    finished_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("finished_products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=True)  # Маркетплейс/покупатель
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str] = mapped_column(Text, nullable=True)


class StockMovement(Base):
    """Движения склада (универсальная таблица для всех операций)."""
    __tablename__ = "stock_movements"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType), nullable=False)
    
    # Ссылки на материалы (заполняется в зависимости от типа операции)
    raw_material_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_materials.id"), nullable=True)
    semi_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("semi_products.id"), nullable=True)
    finished_product_id: Mapped[int] = mapped_column(Integer, ForeignKey("finished_products.id"), nullable=True)
    
    quantity: Mapped[float] = mapped_column(Float, nullable=False)  # Количество (+ приход, - расход)
    
    # Ссылки на операции
    production_id: Mapped[int] = mapped_column(Integer, ForeignKey("productions.id"), nullable=True)
    packing_id: Mapped[int] = mapped_column(Integer, ForeignKey("packings.id"), nullable=True)
    shipment_id: Mapped[int] = mapped_column(Integer, ForeignKey("shipments.id"), nullable=True)
    
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Relationships
    raw_material = relationship("RawMaterial", back_populates="movements")
    semi_product = relationship("SemiProduct", back_populates="movements")
    finished_product = relationship("FinishedProduct", back_populates="movements")
