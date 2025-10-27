"""
Кастомные исключения для приложения Helmitex Warehouse.
"""

class WarehouseException(Exception):
    """Базовое исключение для всех ошибок приложения."""
    pass


class DatabaseError(WarehouseException):
    """Ошибки работы с базой данных."""
    pass


class ValidationError(WarehouseException):
    """Ошибки валидации данных."""
    pass


class SKUError(WarehouseException):
    """Ошибки работы с номенклатурой."""
    pass


class SKUNotFoundError(SKUError):
    """SKU не найден в базе данных."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"SKU с кодом '{code}' не найден")


class SKUAlreadyExistsError(SKUError):
    """SKU с таким кодом уже существует."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"SKU с кодом '{code}' уже существует")


class CategoryError(WarehouseException):
    """Ошибки работы с категориями."""
    pass


class CategoryNotFoundError(CategoryError):
    """Категория не найдена."""
    def __init__(self, category_id: int):
        self.category_id = category_id
        super().__init__(f"Категория с ID {category_id} не найдена")


class RecipeError(WarehouseException):
    """Ошибки работы с рецептурами."""
    pass


class RecipeNotFoundError(RecipeError):
    """Рецепт не найден."""
    def __init__(self, recipe_id: int):
        self.recipe_id = recipe_id
        super().__init__(f"Рецепт с ID {recipe_id} не найден")


class RecipeValidationError(RecipeError):
    """Ошибка валидации рецепта."""
    pass


class ProductionError(WarehouseException):
    """Ошибки производственного процесса."""
    pass


class BarrelError(WarehouseException):
    """Ошибки работы с бочками."""
    pass


class BarrelNotFoundError(BarrelError):
    """Бочка не найдена."""
    def __init__(self, barrel_id: int):
        self.barrel_id = barrel_id
        super().__init__(f"Бочка с ID {barrel_id} не найдена")


class BarrelNotAvailableError(BarrelError):
    """Бочка недоступна для использования."""
    def __init__(self, barrel_id: int, status: str):
        self.barrel_id = barrel_id
        self.status = status
        super().__init__(f"Бочка {barrel_id} недоступна (статус: {status})")


class AuthorizationError(WarehouseException):
    """Ошибки авторизации."""
    def __init__(self, user_id: int, action: str):
        self.user_id = user_id
        self.action = action
        super().__init__(f"Пользователь {user_id} не имеет прав для действия: {action}")
