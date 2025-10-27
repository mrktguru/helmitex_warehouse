from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum

from .db import Base

class SKUType(str, enum.Enum):
    raw = "raw"
    semi = "semi"
    finished = "finished"

class BarrelStatus(str, enum.Enum):
    clean = "clean"
    in_process = "in_process"
    ready = "ready"
    washing = "washing"
    archived = "archived"

class RecipeStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SKU(Base):
    __tablename__ = "skus"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[SKUType] = mapped_column(Enum(SKUType), nullable=False)
    base_unit: Mapped[str] = mapped_column(String(10), nullable=False)  # kg | pcs
    pack_weight_g: Mapped[float | None] = mapped_column(Float, nullable=True)  # only finished
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)  # only raw
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category = relationship("Category")

class Recipe(Base):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"), nullable=False)  # semi
    theoretical_yield_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    status: Mapped[RecipeStatus] = mapped_column(Enum(RecipeStatus), default=RecipeStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product = relationship("SKU")
    components = relationship("RecipeComponent", back_populates="recipe", cascade="all, delete-orphan")

class RecipeComponent(Base):
    __tablename__ = "recipe_components"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    percent: Mapped[float] = mapped_column(Float, nullable=False)

    recipe = relationship("Recipe", back_populates="components")
    category = relationship("Category")

class Barrel(Base):
    __tablename__ = "barrels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    status: Mapped[BarrelStatus] = mapped_column(Enum(BarrelStatus), default=BarrelStatus.clean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SemiBatch(Base):
    __tablename__ = "semi_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"), nullable=False)  # semi
    barrel_id: Mapped[int] = mapped_column(ForeignKey("barrels.id"), nullable=False)
    recipe_id: Mapped[int | None] = mapped_column(ForeignKey("recipes.id"), nullable=True)  # source recipe
    target_mass_kg: Mapped[float] = mapped_column(Float, nullable=False)
    planned_input_kg: Mapped[float] = mapped_column(Float, nullable=False)
    theoretical_yield_pct: Mapped[float] = mapped_column(Float, nullable=False)
    actual_mass_kg: Mapped[float] = mapped_column(Float, nullable=False)
    remainder_kg: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    product = relationship("SKU")
    barrel = relationship("Barrel")
    recipe = relationship("Recipe")
    used_raw = relationship("ProductionUsedRaw", back_populates="batch", cascade="all, delete-orphan")

class ProductionUsedRaw(Base):
    __tablename__ = "production_used_raw"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    semi_batch_id: Mapped[int] = mapped_column(ForeignKey("semi_batches.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    raw_sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"), nullable=False)
    qty_kg: Mapped[float] = mapped_column(Float, nullable=False)

    batch = relationship("SemiBatch", back_populates="used_raw")
    category = relationship("Category")
    raw_sku = relationship("SKU")
