# 🚀 Paku Backend - Comandos Esenciales

## 📚 **DOCUMENTACIÓN TÉCNICA**

### **🛒 Sistema de Carrito (Cart)**
- **[CART_BATCH_OPERATIONS.md](./CART_BATCH_OPERATIONS.md)** - Endpoints y operaciones batch
- **[CART_VALIDATIONS.md](./CART_VALIDATIONS.md)** - Sistema completo de validaciones
- **[CART_IMPLEMENTATION_SUMMARY.md](./CART_IMPLEMENTATION_SUMMARY.md)** - Resumen de implementación
- **[FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md)** - Guía de integración para frontend

### **📱 Flujos de la App**
- **[FLUJO_PAKU_SPA.md](./FLUJO_PAKU_SPA.md)** - Flujo completo frontend → backend

---

## 🧑‍💻 LOCAL (sin Docker, con venv)

### 🐍 Python / venv
```bash
# Crear venv
python -m venv .venv

# Activar venv (Windows)
.\.venv\Scripts\Activate.ps1

# Activar venv (Linux/Mac)
source .venv/bin/activate

# Desactivar venv
deactivate
```

### 🚀 Backend (local)
```bash
# Instalar dependencias
pip install -r requirements.txt

# Levantar API con hot reload
uvicorn app.main:app --reload

# Levantar en host específico (para mobile)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Abrir Swagger
http://127.0.0.1:8000/docs

# Health check
curl http://127.0.0.1:8000/health
```

### 🗄️ Alembic (local)
```bash
# IMPORTANTE: Configurar DATABASE_URL primero
set DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/paku_db

# Verificar esquema de carrito (NO requiere migraciones)
python verify_cart_schema.py

# Ver migración actual
python -m alembic current

# Ver historial completo
python -m alembic history

# Aplicar migraciones pendientes
python -m alembic upgrade head

# Crear migración automática (si hay cambios en modelos)
python -m alembic revision --autogenerate -m "mensaje"

# Crear migración manual (para enums, cambios complejos)
python -m alembic revision -m "fix_cartstatus_enum"

# Downgrade (revertir última migración)
python -m alembic downgrade -1
```

**📋 NOTA:** Las mejoras de validación del carrito NO requieren migraciones.  
Ver [DATABASE_STATUS.md](./DATABASE_STATUS.md) para más detalles.

### 🧪 Tests (local)
```bash
# Ejecutar todos los tests
python -m pytest -q

# Ejecutar tests de módulo específico
python -m pytest tests/test_pets_flow.py -q

# Ejecutar test específico
python -m pytest tests/test_pets_flow.py::test_create_pet -q

# Ver coverage
python -m pytest --cov=app tests/
```

### 🧠 Debug rápido (local)
```bash
# Ver variables de entorno
python -c "import os; from app.core.settings import settings; print(f'DB_URL: {settings.DATABASE_URL}'); print(f'CORS: {settings.CORS_ORIGINS}')"

# Probar conexión a DB
python -c "from app.core.db import engine; print(f'Engine: {engine.url}')"

# Ver modelos detectados por Alembic
python -c "from app.modules.pets.infra.models import PetModel; print('Pets models OK')"
```

## 🖥️ SERVER (con Docker)

### 🐳 Docker
```bash
# Build + levantar todos los servicios
docker compose up -d --build

# Ver contenedores activos
docker compose ps

# Reiniciar backend específico
docker compose restart paku-backend

# Detener todo
docker compose down

# Ver logs en tiempo real
docker compose logs -f
```

### 🗄️ Alembic (server)
```bash
# Ejecutar migraciones en producción
docker compose exec paku-backend alembic upgrade head

# Ver versión actual
docker compose exec paku-backend alembic current

# Crear migración (desde server)
docker compose exec paku-backend alembic revision --autogenerate -m "server_change"

# Ver historial
docker compose exec paku-backend alembic history
```

### 🗃️ Postgres (server)
```bash
# Conectar a la base de datos
docker exec -it paku-db psql -U paku_user -d paku_db

# Ver todas las tablas
docker exec -it paku-db psql -U paku_user -d paku_db -c "\dt"

# Inspeccionar tabla específica
docker exec -it paku-db psql -U paku_user -d paku_db -c "\d cart_sessions"

# Ver estructura completa
docker exec -it paku-db psql -U paku_user -d paku_db -c "\d+ pets"

# Contar registros
docker exec -it paku-db psql -U paku_user -d paku_db -c "SELECT COUNT(*) FROM pets;"
```

### 📜 Logs (server)
```bash
# Logs del backend en tiempo real
docker compose logs -f paku-backend

# Últimas 100 líneas
docker compose logs --tail=100 paku-backend

# Filtrar por cleanup (scheduler)
docker compose logs --tail=200 paku-backend | grep -i "cleanup"

# Solo errores
docker compose logs --tail=200 paku-backend | grep -i "error\|traceback"

# Logs de todos los servicios
docker compose logs -f --tail=50
```

## 🎯 Módulos y Endpoints Clave

### 🐾 Pets
```bash
# GET /pets (listado del usuario)
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/pets?limit=10&offset=0

# POST /pets (crear)
curl -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{"name":"Fido","species":"dog","breed":"Labrador"}' \
  http://localhost:8000/pets
```

### 🛒 Cart
```bash
# Ver carrito actual
curl -H "Authorization: Bearer TOKEN" http://localhost:8000/cart

# Checkout
curl -X POST -H "Authorization: Bearer TOKEN" http://localhost:8000/cart/checkout
```

### 🔐 Auth
```bash
# Login
curl -X POST -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  http://localhost:8000/auth/login
```

## 🚨 Problemas Comunes y Soluciones

### ❌ "type cartstatus does not exist"
```bash
# Solución: Migración explícita del enum
docker compose exec paku-backend alembic upgrade head
# Si falla, crear migración manual para el enum
```

### ❌ "no such table: services"
```bash
# Solución: Aplicar migración inicial
docker compose exec paku-backend alembic upgrade eae7270101c6
```

### ❌ "DATABASE_URL is required"
```bash
# Local: Configurar variable
set DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/paku_db

# Server: Ya está en docker-compose.yml
```

### ❌ CORS en React Native
```bash
# Ver configuración CORS
curl -H "Origin: exp://192.168.1.100:8081" http://localhost:8000/pets
# Debe devolver 200 con headers CORS
```

## 🧠 Reglas de Oro del Proyecto

### 📦 Alembic
- **Local**: `python -m alembic ...`
- **Server**: `docker compose exec paku-backend alembic ...`
- **Enums rotos**: Crear migración explícita (no autogenerate)
- **SQLite fallback**: Siempre verificar `DATABASE_URL`

### 🔐 Autenticación
- Todos los endpoints protegidos usan `CurrentUser = Depends(get_current_user)`
- Header: `Authorization: Bearer <token>`
- Login: `POST /auth/login`

### 🐾 Pets Module
- Listado: `GET /pets?limit=7&offset=0` (requiere auth)
- Crear: `POST /pets` (requiere auth)
- Solo mascotas del usuario autenticado

### 🛒 Cart Module
- Usa TTL de 2 horas
- Cleanup automático cada 5 minutos
- Estados: `active`, `checked_out`, `expired`, `cancelled`

---

## 📍 Geo Module (Districts)

### Overview
The **Geo** module provides a catalog of geographic districts (distritos) for address validation.

**⚠️ IMPORTANT:** Districts are currently **HARDCODED** (no database required).

### How it works
- Districts are defined in `app/modules/geo/infra/districts_data.py`
- No need to populate `geo_districts` table
- API endpoints work immediately without DB seed

### Available Districts (MVP)
```python
# Currently supporting 3 districts in Lima:
- Barranco (150104)
- Jesús María (150113)
- Lince (150116)
```

### API Endpoints
```bash
# List all active districts
GET /geo/districts?active=true

# Get specific district
GET /geo/districts/150104
```

### Testing
```bash
# Test districts without database
python test_hardcoded_districts.py
```

### Adding New Districts
Edit `app/modules/geo/infra/districts_data.py`:
```python
DISTRICTS_DATA = [
    # ... existing districts
    {
        "id": "150114",  # UBIGEO from INEI
        "name": "La Molina",
        "province_name": "Lima",
        "department_name": "Lima",
        "active": True,
    },
]
```

No migration needed! Restart server and new district is available.

### Future: Database Migration
When ready to use database:
1. Populate `geo_districts` table (migration already exists)
2. Update `repository.py` to query DB
3. No changes needed in other modules (same interface)

See full documentation: `app/modules/geo/README.md`

---

## 🔄 Workflow Típico

### 1. Nuevo desarrollo local
```bash
# 1. Activar venv
.\.venv\Scripts\Activate.ps1

# 2. Levantar DB local (PostgreSQL)
# 3. Configurar DATABASE_URL
set DATABASE_URL=postgresql+asyncpg://localhost/paku_dev

# 4. Aplicar migraciones
python -m alembic upgrade head

# 5. Levantar backend
uvicorn app.main:app --reload

# 6. Probar en Swagger
# http://127.0.0.1:8000/docs
```

### 2. Deploy a server
```bash
# 1. Push cambios
git add . && git commit -m "feature" && git push

# 2. Build y deploy
docker compose up -d --build

# 3. Migraciones
docker compose exec paku-backend alembic upgrade head

# 4. Verificar
curl http://tu-servidor:8000/health
```

### 3. Debug en producción
```bash
# 1. Ver logs
docker compose logs --tail=100 paku-backend | grep -i error

# 2. Ver DB
docker exec -it paku-db psql -U paku_user -d paku_db -c "\dt"

# 3. Probar endpoint
curl -H "Authorization: Bearer TOKEN" http://tu-servidor:8000/pets
```

---

**🎯 Recuerda**: Este proyecto usa SQLAlchemy puro (no SQLModel), AsyncSession, y arquitectura por módulos (Domain → App → Infra → API).
