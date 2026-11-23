import os
from dotenv import load_dotenv

load_dotenv()

SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8001"))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))
DATASET_PATH = os.getenv("DATASET_PATH", "/app/data/dataset_agro.csv")
MODEL_DIR = os.getenv("MODEL_DIR", "/app/models")
STATS_FILE = os.getenv("STATS_FILE", "/app/data/historial.json")
