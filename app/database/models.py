"""
Модели базы данных для Helmitex Warehouse.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum

from app.database.db import Base


class SKUType(str, enum.Enum):
    """Типы номенклатуры."""
    raw = "raw"          # Сырье
    semi = "semi"        # Полуфабрикат
    finished = "finished"  # Готовая продукция


class RecipeStatus(str, enum.Enum):
    """Статусы рецептов."""
    draft = "draft"      # Черновик
    active = "active"    # Активный
    archived = "archived"  # Архивный


class BarrelStatus(str, enum.Enum):
    """Статусы бочек."""
    clean = "clean"          # Чистая
    in_process = "in_process"  # В процессе
    ready = "ready"          # Готова
    washing = "washing"      # Моется
    archived = "archived"    # Архивная


class Category(Base):
    """Категории сырья."""
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    skus = relationship("SKU", back_populates="category")


class SKU(Base):
    """Номенклатура (Stock Keeping Unit)."""
    __tablename__ = "skus"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[SKUType] = mapped_column(Enum(SKUType), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # кг, л, шт
    package_weight: Mapped[float] = mapped_column(Float, nullable=True)  # Вес упаковки
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="skus")
    recipe_components = relationship("RecipeComponent", back_populates="raw_sku")
    recipes = relationship("Recipe", back_populates="semi_sku")


class Recipe(Base):
    """Технологическая карта (рецепт)."""
    __tablename__ = "recipes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    semi_sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False)
    status: Mapped[RecipeStatus] = mapped_column(
        Enum(RecipeStatus), 
        default=RecipeStatus.draft, 
        nullable=False
    )
    theoretical_yield: Mapped[float] = mapped_column(Float, nullable=False)  # % выхода
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    semi_sku = relationship("SKU", back_populates="recipes")
    components = relationship("RecipeComponent", back_populates="recipe", cascade="all, delete-orphan")
    productions = relationship("Production", back_populates="recipe")


class RecipeComponent(Base):
    """Компоненты рецепта."""
    __tablename__ = "recipe_components"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"), nullable=False)
    raw_sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)  # % в рецепте
    
    # Relationships
    recipe = relationship("Recipe", back_populates="components")
    raw_sku = relationship("SKU", back_populates="recipe_components")


class Barrel(Base):
    """Бочки для производства."""
    __tablename__ = "barrels"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[BarrelStatus] = mapped_column(
        Enum(BarrelStatus), 
        default=BarrelStatus.clean, 
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    productions = relationship("Production", back_populates="barrel")


class Production(Base):
    """Производственные операции."""
    __tablename__ = "productions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipe_id: Mapped[int] = mapped_column(Integer, ForeignKey("recipes.id"), nullable=False)
    barrel_id: Mapped[int] = mapped_column(Integer, ForeignKey("barrels.id"), nullable=False)
    operator_telegram_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_weight: Mapped[float] = mapped_column(Float, nullable=False)  # Целевой вес
    actual_weight: Mapped[float] = mapped_column(Float, nullable=True)  # Фактический вес
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    recipe = relationship("Recipe", back_populates="productions")
    barrel = relationship("Barrel", back_populates="productions")
    used_raw = relationship("ProductionUsedRaw", back_populates="production", cascade="all, delete-orphan")


class ProductionUsedRaw(Base):
    """Использованное сырье в производстве."""
    __tablename__ = "production_used_raw"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    production_id: Mapped[int] = mapped_column(Integer, ForeignKey("productions.id"), nullable=False)
    raw_sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Relationships
    production = relationship("Production", back_populates="used_raw")


class SemiBatch(Base):
    """Партии полуфабрикатов."""
    __tablename__ = "semi_batches"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    semi_sku_id: Mapped[int] = mapped_column(Integer, ForeignKey("skus.id"), nullable=False)
    barrel_id: Mapped[int] = mapped_column(Integer, ForeignKey("barrels.id"), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
