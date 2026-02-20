#!/usr/bin/env python
"""
Script de verificación de esquema de BD para Cart module.

Este script verifica que el esquema actual de la BD coincida con los modelos.
Si encuentra diferencias, generará una migración automática.

Uso:
    python verify_cart_schema.py
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.modules.cart.infra.models import CartSessionModel, CartItemModel
from app.core.db import engine
from sqlalchemy import inspect


async def verify_schema():
    """Verifica que las tablas existan y tengan las columnas correctas."""
    
    print("🔍 Verificando esquema de carrito...\n")
    
    inspector = inspect(engine.sync_engine)
    
    # Verificar cart_sessions
    print("📋 Tabla: cart_sessions")
    if inspector.has_table("cart_sessions"):
        print("   ✅ Existe")
        columns = [col['name'] for col in inspector.get_columns("cart_sessions")]
        print(f"   Columnas: {', '.join(columns)}")
        
        expected_columns = {'id', 'user_id', 'status', 'expires_at', 'created_at', 'updated_at'}
        missing = expected_columns - set(columns)
        if missing:
            print(f"   ⚠️  Columnas faltantes: {missing}")
        else:
            print("   ✅ Todas las columnas presentes")
        
        # Verificar índices
        indexes = inspector.get_indexes("cart_sessions")
        print(f"   Índices: {len(indexes)} encontrados")
        for idx in indexes:
            print(f"      - {idx['name']}: {idx['column_names']}")
    else:
        print("   ❌ No existe")
    
    print("\n📋 Tabla: cart_items")
    if inspector.has_table("cart_items"):
        print("   ✅ Existe")
        columns = [col['name'] for col in inspector.get_columns("cart_items")]
        print(f"   Columnas: {', '.join(columns)}")
        
        expected_columns = {'id', 'cart_id', 'kind', 'ref_id', 'name', 'qty', 'unit_price', 'meta', 'created_at'}
        missing = expected_columns - set(columns)
        if missing:
            print(f"   ⚠️  Columnas faltantes: {missing}")
        else:
            print("   ✅ Todas las columnas presentes")
        
        # Verificar índices
        indexes = inspector.get_indexes("cart_items")
        print(f"   Índices: {len(indexes)} encontrados")
        for idx in indexes:
            print(f"      - {idx['name']}: {idx['column_names']}")
    else:
        print("   ❌ No existe")
    
    # Verificar enums
    print("\n📋 Enums:")
    enums = inspector.get_enums()
    if enums:
        for enum in enums:
            if enum['name'] in ['cartstatus', 'cartitemkind']:
                print(f"   ✅ {enum['name']}: {enum['labels']}")
    else:
        print("   ⚠️  No se pudieron verificar enums (puede ser limitación del inspector)")
    
    print("\n" + "="*60)
    print("✅ Verificación completada")
    print("="*60)
    print("\nSi todo está ✅, NO se requieren migraciones.")
    print("Si hay ⚠️ o ❌, ejecuta:")
    print("  alembic revision --autogenerate -m 'fix cart schema'")
    print("  alembic upgrade head")


if __name__ == "__main__":
    import asyncio
    asyncio.run(verify_schema())
