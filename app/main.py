from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.core.scheduler import start_scheduler, stop_scheduler

from app.modules.booking.api.router import router as booking_router
from app.modules.cart.api.router import router as cart_router
from app.modules.clinical_history.api.router import router as clinical_history_router
from app.modules.commerce.api.router import router as commerce_router
from app.modules.geo.api.router import router as geo_router
from app.modules.iam.api.router import router as iam_router
from app.modules.notifications.api.router import router as notifications_router
from app.modules.orders.api.router import router as orders_router
from app.modules.pets.api.router import router as pets_router
from app.modules.push.api.router import router as push_router
from app.modules.wallet.api.router import router as wallet_router
from app.media.router import router as media_router
from app.modules.catalog.api.router import router as catalog_router
from app.modules.paku_spa.api.router import router as paku_spa_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
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

app.include_router(geo_router, prefix="/geo")
app.include_router(catalog_router)
app.include_router(paku_spa_router)
app.include_router(iam_router)
app.include_router(pets_router)
app.include_router(commerce_router)
app.include_router(booking_router)
app.include_router(clinical_history_router)
app.include_router(wallet_router)
app.include_router(notifications_router)
app.include_router(cart_router)
app.include_router(push_router)
app.include_router(orders_router)
app.include_router(media_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.ENV
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
