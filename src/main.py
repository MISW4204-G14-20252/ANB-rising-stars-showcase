from fastapi import FastAPI
from src.routers.auth_router import auth_router
from src.db.database import engine
from src.models import db_models

# import models to create tables
db_models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

app.include_router(router = auth_router, prefix="/api/auth")
