"""
Обработчики процесса прихода сырья.

Состояния ConversationHandler:
- SELECT_CATEGORY: Выбор категории сырья
- SELECT_RAW_MATERIAL: Выбор конкретного сырья
- INPUT_QUANTITY: Ввод количества
- CONFIRM_ARRIVAL: Подтверждение операции

Функции:
- arrival_menu_callback() - меню прихода
- arrival_start() - начало процесса
- category_selected() - выбрана категория
- raw_material_selected() - выбрано сырье
- quantity_entered() - введено количество
- confirm_arrival() - подтверждение
- execute_arrival() - выполнение транзакции
- cancel_arrival() - отмена операции
"""
