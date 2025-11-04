"""
Обработчики процесса производства (замес бочек).

Состояния ConversationHandler:
- SELECT_RECIPE: Выбор технологической карты
- INPUT_TARGET_WEIGHT: Ввод целевого веса
- CHECK_AVAILABILITY: Проверка наличия сырья
- RECALCULATE_OR_PROCEED: Пересчет/продолжение
- CONFIRM_PRODUCTION: Подтверждение
- ENTER_ACTUAL_WEIGHT: Ввод фактического веса бочки

Функции:
- production_menu_callback()
- production_start()
- recipe_selected()
- target_weight_entered()
- check_raw_materials_availability()
- recalculate_to_available()
- confirm_production()
- actual_weight_entered()
- execute_production() - создание бочки, списание сырья
- cancel_production()
"""
