from fastapi import FastAPI
from src.routers.auth_router import auth_router
from src.db.database import engine
from src.models import db_models
from src.routers import videos_router


# import models to create tables
db_models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

app.include_router(router = auth_router, prefix="/api/auth")

app.include_router(router = videos_router.router)  # No prefix here, as it's already defined in the router itself