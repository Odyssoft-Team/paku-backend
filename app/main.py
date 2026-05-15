import json
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.settings import settings
from app.core.scheduler import start_scheduler, stop_scheduler

from app.modules.booking.api.router import router as booking_router
from app.modules.cart.api.router import router as cart_router
from app.modules.geo.api.router import router as geo_router
from app.modules.iam.api.router import (
    router as iam_router,
    admin_router as iam_admin_router,
)
from app.modules.iam.api.social_router import router as iam_social_router
from app.modules.notifications.api.router import router as notifications_router
from app.modules.orders.api.router import (
    router as orders_router,
    admin_router as orders_admin_router,
)
from app.modules.pets.api.router import (
    router as pets_router,
    admin_router as pets_admin_router,
)
from app.modules.pet_records.api.router import router as pet_records_router
from app.modules.push.api.router import router as push_router
from app.modules.wallet.api.router import router as wallet_router
from app.media.router import router as media_router
from app.modules.catalog.api.router import (
    router as catalog_router,
    admin_router as catalog_admin_router,
)
from app.modules.store.api.router import (
    router as store_router,
    admin_router as store_admin_router,
)
from app.modules.chat.api.router import router as chat_router
from app.modules.streaming.api.router import router as streaming_router
from app.modules.tracking.api.router import router as tracking_router


def _init_firebase() -> None:
    """Inicializa Firebase Admin SDK.

    - Sin FIREBASE_CREDENTIALS_JSON → usa Application Default Credentials (ADC).
      En GCP la VM usa automáticamente su service account. No requiere configuración extra.
    - Con FIREBASE_CREDENTIALS_JSON → usa el JSON explícito (útil en local / CI).
    """
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            if settings.FIREBASE_CREDENTIALS_JSON:
                creds_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
                cred = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(cred)
                logging.info("Firebase Admin SDK initialized with service account JSON")
            else:
                firebase_admin.initialize_app()
                logging.info(
                    "Firebase Admin SDK initialized with ADC (GCP VM identity)"
                )
    except Exception as exc:
        logging.error(f"Failed to initialize Firebase Admin SDK: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_firebase()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
    root_path=settings.ROOT_PATH,
)

# CORS configuration
origins = settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Avoid invalid CORS config: "*" cannot be used with credentials
    allow_credentials=("*" not in origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Usar X-Request-ID si ya viene del cliente, sino generar uno
        req_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        # Exponerlo en la respuesta para facilitar correlación en logs
        response.headers["X-Request-ID"] = req_id
        return response


app.add_middleware(RequestIDMiddleware)

app.include_router(geo_router, prefix="/geo")
app.include_router(catalog_router)
app.include_router(iam_router)
app.include_router(iam_social_router)
app.include_router(pets_router)
app.include_router(pet_records_router)
app.include_router(booking_router)
app.include_router(wallet_router)
app.include_router(notifications_router)
app.include_router(cart_router)
app.include_router(push_router)
app.include_router(orders_router)
app.include_router(store_router)
app.include_router(streaming_router)
app.include_router(chat_router)
app.include_router(tracking_router)
app.include_router(orders_admin_router, prefix="/admin")
app.include_router(catalog_admin_router, prefix="/admin")
app.include_router(iam_admin_router, prefix="/admin")
app.include_router(pets_admin_router, prefix="/admin")
app.include_router(store_admin_router, prefix="/admin")
app.include_router(media_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENV}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
