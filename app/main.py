from fastapi import FastAPI

from app.core.settings import settings
from app.modules.iam.api.router import router as iam_router


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG
)

app.include_router(iam_router)


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
