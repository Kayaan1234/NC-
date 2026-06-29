import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference
from backend.routers.auth import router as auth_router
from backend.routers.users import router as user_router

from backend.core.config import settings
from backend.database import engine, Base

# Dev convenience: auto-create tables. For the Postgres cutover, replace this
# with Alembic migrations and remove the call (see prod next-steps).
Base.metadata.create_all(bind=engine)


app = FastAPI()
app.include_router(auth_router)
app.include_router(user_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],)


@app.get("/health", tags=["Health"])
def health():
    """Liveness probe for load balancers / orchestrators."""
    return {"status": "ok"}


@app.get("/scalar")
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title = "Scalar API",
    )

    

