"""
Обработчики процесса отгрузки.

Состояния ConversationHandler:
- SELECT_FINISHED_PRODUCT: Выбор готовой продукции
- INPUT_QUANTITY: Ввод количества
- INPUT_RECIPIENT: Ввод получателя (опционально)
- CONFIRM_SHIPMENT: Подтверждение

Функции:
- shipment_menu_callback()
- shipment_start()
- finished_product_selected()
- quantity_entered()
- recipient_entered()
- confirm_shipment()
- execute_shipment()
- cancel_shipment()
"""
