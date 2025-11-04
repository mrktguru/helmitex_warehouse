"""Add production logic: barrels, recipes, packing, shipment

Revision ID: 20250204_001
Revises: 20250127_initial_migration
Create Date: 2025-02-04 12:00:00
"""
# Добавление таблиц:
# - technological_cards
# - recipe_components
# - production_batches
# - barrels
# - packing_variants
# - recipients
# - shipments
# - shipment_items
# - inventory_reserves
# - waste_records
# Обновление enum SKUType (добавить 'semi')
# Обновление enum MovementType (добавить 'production', 'packing', 'shipment', 'waste')
