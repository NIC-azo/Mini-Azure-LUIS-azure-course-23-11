from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import SERVER_PORT, SERVER_HOST

app = FastAPI(
    title="Mini-Azure LUIS API",
    description="Motor NLP Local para Agroexportación (FastAPI + Scikit-Learn)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Mini-Azure LUIS NLP Engine",
        "port": SERVER_PORT,
        "host": SERVER_HOST
    }
