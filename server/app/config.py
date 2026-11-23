import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz o entorno actual
load_dotenv()

# BASE_DIR apunta a la carpeta 'server'
BASE_DIR = Path(__file__).resolve().parent.parent

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8001"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))

def resolve_path(env_var_name: str, fallback_subpath: str) -> str:
    val = os.getenv(env_var_name)
    if val and os.path.exists(val):
        return val
    # Si viene configurado como /app/... (entorno Docker) pero corre fuera del contenedor
    if val and val.startswith("/app/"):
        rel = val[len("/app/"):]
        candidate = BASE_DIR / rel
        if candidate.exists() or candidate.parent.exists():
            return str(candidate)
    fallback = BASE_DIR / fallback_subpath
    return str(fallback)

DATASET_PATH = resolve_path("DATASET_PATH", "data/dataset_agro.csv")
MODEL_DIR = resolve_path("MODEL_DIR", "models")
STATS_FILE = resolve_path("STATS_FILE", "data/historial.json")
