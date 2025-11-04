"""
Обработчики процесса фасовки.

Состояния ConversationHandler:
- SELECT_SEMI_PRODUCT: Выбор полуфабриката
- SELECT_FINISHED_PRODUCT: Выбор готовой продукции
- INPUT_UNITS_COUNT: Ввод количества упаковок
- CONFIRM_PACKING: Подтверждение

Функции:
- packing_menu_callback()
- packing_start()
- semi_product_selected()
- finished_product_selected()
- units_count_entered()
- confirm_packing()
- execute_packing() - FIFO списание бочек, оприходование готовой продукции
- cancel_packing()
"""
