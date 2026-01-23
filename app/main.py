from fastapi import FastAPI

from app.core.settings import settings
from app.modules.booking.api.router import router as booking_router
from app.modules.clinical_history.api.router import router as clinical_history_router
from app.modules.iam.api.router import router as iam_router
from app.modules.notifications.api.router import router as notifications_router
from app.modules.pets.api.router import router as pets_router
from app.modules.commerce.api.router import router as commerce_router
from app.modules.wallet.api.router import router as wallet_router


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG
)

app.include_router(iam_router)
app.include_router(pets_router)
app.include_router(commerce_router)
app.include_router(booking_router)
app.include_router(clinical_history_router)
app.include_router(wallet_router)
app.include_router(notifications_router)


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
        reload=settings.DEBUG
    )
